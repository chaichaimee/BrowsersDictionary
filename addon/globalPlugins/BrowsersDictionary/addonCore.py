# addonCore.py

import logging
import re
import time
import threading

import wx

import addonHandler
import globalPluginHandler
import api
import ui
import core
import controlTypes
from scriptHandler import script
from logHandler import log
from comtypes import COMError
import gui as nvdaGui
from speech.extensions import filter_speechSequence

from .manager import BrowsersDictionaryConfig
from .gui import MainDialog, AddSiteDialog

addonHandler.initTranslation()

DOUBLE_TAP_THRESHOLD = 0.4
URL_UPDATE_INTERVAL = 0.5
BROWSER_APPS = {"firefox", "chrome", "msedge", "brave", "opera", "iexplore"}

# Hard cap on how long, in total, the regex entries for a single spoken
# chunk are allowed to run. Once exceeded, remaining regex entries for
# that chunk are skipped. This bounds the cumulative cost of several
# moderate patterns; it cannot interrupt a single pattern that is already
# executing (Python's re module has no preemptive timeout), so pattern
# safety is additionally checked at save time in the settings dialog.
REGEX_TIME_BUDGET_SECONDS = 0.1

# A spoken chunk longer than this is not scanned for replacements at all;
# such chunks are rare in practice and scanning them adds cost for no
# realistic benefit.
MAX_SCANNED_TEXT_LENGTH = 20000


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Browsers Dictionary")

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		self.config = BrowsersDictionaryConfig()
		self._last_tap_time = 0
		self._tap_count = 0
		self._pending_action = None
		self._cached_url = None
		self._url_lock = threading.Lock()
		self._is_target_active = False
		self._last_url_update_time = 0
		self._shutdown_event = threading.Event()
		filter_speechSequence.register(self._onFilterSpeechSequence)

	def terminate(self):
		self._shutdown_event.set()
		filter_speechSequence.unregister(self._onFilterSpeechSequence)
		self._cached_url = None

	def _onFilterSpeechSequence(self, speechSequence):
		# The cached URL is only meaningful while the currently focused app
		# is actually one of the tracked browsers - it is deliberately never
		# cleared on a plain focus/app switch (see event_foreground/
		# event_gainFocus), so without this check the last browser URL kept
		# being applied to speech in any other application (e.g. Notepad++)
		# after switching away, which is why word rules were affecting
		# every app instead of only browsers.
		if not self._is_target_active:
			return speechSequence
		with self._url_lock:
			currentUrl = self._cached_url
		if not currentUrl:
			return speechSequence

		siteData = self.config.get_site_by_url(currentUrl)
		if not siteData:
			# Temporary diagnostic (Section 20): confirms whether the cached
			# URL is even reaching a configured site at all. Remove once the
			# "messages until" root cause is confirmed and closed.
			if log.isEnabledFor(logging.DEBUG):
				log.debug(f"BrowsersDictionary: no site configured for current URL ({currentUrl[:80]!r})")
			return speechSequence

		wordsData = siteData.get("words", [])
		if not wordsData:
			return speechSequence

		if log.isEnabledFor(logging.DEBUG):
			log.debug(
				f"BrowsersDictionary: matched site '{siteData.get('display_name', '?')}' "
				f"with {len(wordsData)} entrie(s) for URL ({currentUrl[:80]!r})"
			)

		# A dictionary pattern is matched against a run of adjacent string
		# items joined together, not against each item in isolation. NVDA
		# frequently splits a single spoken utterance into several plain
		# string items with no separating command between them - e.g. a
		# link's role name, the link's own text, and any trailing text
		# after it arrive as three consecutive strings. A pattern spanning
		# exactly that kind of boundary (e.g. "messages until", where
		# "messages" is a link's text and " until ..." is the text that
		# follows the link) could never match when each item was scanned
		# on its own, which was the confirmed cause of such patterns
		# silently never firing. Non-string items (LangChangeCommand,
		# PitchCommand, etc.) still act as hard boundaries and are never
		# merged across.
		filteredSequence = []
		textRun = []
		for item in speechSequence:
			if isinstance(item, str):
				textRun.append(item)
				continue
			filteredSequence.extend(self._flush_text_run(textRun, wordsData))
			textRun = []
			filteredSequence.append(item)
		filteredSequence.extend(self._flush_text_run(textRun, wordsData))
		return filteredSequence

	def _flush_text_run(self, text_run, words_data):
		if not text_run:
			return []
		joinedText = "".join(text_run)
		replacedText = self._apply_word_replacements(joinedText, words_data)
		if replacedText == joinedText:
			# Nothing matched - hand the original items back unmodified so a
			# run with no applicable pattern keeps its exact prior shape
			# instead of being needlessly collapsed into one string.
			return list(text_run)
		if log.isEnabledFor(logging.DEBUG):
			log.debug(f"BrowsersDictionary: applied dictionary, {joinedText[:80]!r} -> {replacedText[:80]!r}")
		return [replacedText]

	def _apply_word_replacements(self, text, words_data):
		if not text or len(text) > MAX_SCANNED_TEXT_LENGTH:
			return text

		result_text = text
		literal_entries = []
		regex_patterns = []

		for word_data in words_data:
			value = word_data.get("value")
			is_regex = word_data.get("is_regex", False)
			replacement = word_data.get("replacement", "")
			# A blank replacement is a deliberate value, not "not configured
			# yet" - it means "silence this pattern", matching how NVDA's
			# own built-in speech dictionary treats a blank replacement
			# field. Handing it to .replace()/re.sub() with an empty
			# replacement string is exactly the correct behavior here, so
			# only a genuinely blank pattern value is skipped.
			if not value:
				continue
			if is_regex:
				regex_patterns.append((value, replacement))
			else:
				literal_entries.append((value, replacement))

		if literal_entries:
			literal_entries.sort(key=lambda entry: len(entry[0]), reverse=True)
			for word, repl in literal_entries:
				result_text = result_text.replace(word, repl)

		elapsedBudget = 0.0
		for pattern, repl in regex_patterns:
			if elapsedBudget >= REGEX_TIME_BUDGET_SECONDS:
				log.warning("BrowsersDictionary: Regex time budget exhausted, skipping remaining entries for this utterance")
				break
			startTime = time.time()
			try:
				result_text = re.sub(pattern, repl, result_text)
			except re.error as err:
				log.error(f"BrowsersDictionary: Invalid regex skipped: {pattern[:50]} - {err}")
			except (RuntimeError, ValueError) as err:
				log.error(f"BrowsersDictionary: Regex execution error: {err}")
			finally:
				elapsedBudget += time.time() - startTime

		return result_text

	def event_foreground(self, obj, nextHandler):
		nextHandler()
		if self._is_browser_app(obj):
			self._is_target_active = True
			self._last_url_update_time = 0  # force immediate update
			self._update_url_async(obj)
		else:
			self._is_target_active = False

	def event_documentLoadComplete(self, obj, nextHandler):
		nextHandler()
		if not self._is_target_active:
			return
		# event_gainFocus can fire while the browser is still mid-navigation,
		# before the treeInterceptor's documentConstantIdentifier has been
		# finalized for the new page; the extraction thread then either reads
		# the previous page's identifier or finds none at all. If no further
		# focus change happens inside the new page (common for a static
		# article/document), nothing ever re-triggers an update, so the
		# cached URL is left pointing at the wrong page until an unrelated
		# event (e.g. a foreground switch) forces a re-check. documentLoadComplete
		# only fires once the document is actually finished loading, so the
		# identifier is guaranteed valid at this point; forcing an immediate,
		# unthrottled re-check here closes the race at its source instead of
		# masking it with a retry loop or a delay.
		self._last_url_update_time = 0
		self._update_url_async(obj)

	def event_gainFocus(self, obj, nextHandler):
		nextHandler()
		if not self._is_target_active:
			return
		current_time = time.time()
		if current_time - self._last_url_update_time < URL_UPDATE_INTERVAL:
			return
		self._last_url_update_time = current_time
		self._update_url_async(obj)

	def _is_browser_app(self, obj):
		try:
			app_name = getattr(obj, 'appModule', None) and obj.appModule.appName
			return app_name and app_name.lower() in BROWSER_APPS
		except (AttributeError, RuntimeError):
			return False

	def _update_url_async(self, obj):
		if self._shutdown_event.is_set():
			return
		# target_obj (and its .treeInterceptor/.role/.UIAElement properties,
		# read inside _perform_url_extraction) wrap COM/IAccessible2 pointers
		# that are apartment-bound to NVDA's own main-thread STA. Even just
		# reading the .treeInterceptor property can trigger a live
		# containment check against the document (Gecko_ia2.__contains__ for
		# Firefox), which is itself a COM call - not a plain attribute read.
		# A bare threading.Thread has no COM apartment of its own, so any of
		# these reads from it produce a "marshalled for a different thread"
		# COMError; this was confirmed directly in production logs against
		# the previous background-thread implementation, on this exact
		# worker. The failure was silently swallowed by the broad except
		# below, leaving the cached URL stale - which was the real cause of
		# the reported "have to switch windows to fix it" symptom, not just
		# the event-timing race addressed earlier. core.callLater defers the
		# same work onto the main thread's own processing loop instead:
		# still non-blocking relative to the calling event handler, but now
		# on the one thread where these COM pointers are actually valid.
		core.callLater(0, self._perform_url_extraction, obj)

	def _perform_url_extraction(self, target_obj):
		if self._shutdown_event.is_set():
			return
		try:
			url = None
			ti = getattr(target_obj, 'treeInterceptor', None)
			if ti and hasattr(ti, 'documentConstantIdentifier'):
				candidate = ti.documentConstantIdentifier
				if candidate and isinstance(candidate, str) and (candidate.startswith('http') or candidate.startswith('file')):
					url = candidate

			# EDIT/COMBOBOX controls are only worth reading when they are still the
			# genuine, current focus. This thread runs concurrently with focus recovery
			# logic in other add-ons (e.g. an unexpected editable focus being corrected),
			# so target_obj can go stale or get its underlying COM pointer detached
			# between when this thread was started and when it actually reaches the UIA
			# property read below. Re-checking real focus immediately beforehand avoids
			# racing a COM call against an object that is no longer valid.
			if not url and self._objectStillHasRealFocus(target_obj):
				objRole = getattr(target_obj, 'role', None)
				if objRole in (controlTypes.Role.EDIT, controlTypes.Role.COMBOBOX):
					try:
						uia_elem = getattr(target_obj, 'UIAElement', None)
						if uia_elem and self._objectStillHasRealFocus(target_obj):
							val = uia_elem.CurrentValue
							if val and isinstance(val, str) and (val.startswith('http') or val.startswith('file')):
								url = val
					except (COMError, AttributeError, RuntimeError, ValueError, OSError):
						pass

			if url:
				core.callLater(0, self._set_cached_url, url)
		except (COMError, AttributeError, RuntimeError, ValueError, OSError) as err:
			log.debug(f"BrowsersDictionary: URL extraction error: {err}")

	def _objectStillHasRealFocus(self, target_obj):
		try:
			focusObj = api.getFocusObject()
		except (COMError, AttributeError, RuntimeError):
			return False
		if focusObj is None:
			return False
		try:
			return focusObj == target_obj
		except (COMError, AttributeError, RuntimeError):
			return False

	def _set_cached_url(self, url):
		with self._url_lock:
			self._cached_url = url

	def get_current_url(self):
		with self._url_lock:
			return self._cached_url

	@script(
		description=_("Open Browsers Dictionary settings (single tap), add new site (double tap), or edit current site (triple tap)"),
		gesture="kb:alt+windows+B",
		category=_("Browsers Dictionary")
	)
	def script_openSettings(self, gesture):
		currentTime = time.time()
		if currentTime - self._last_tap_time > DOUBLE_TAP_THRESHOLD:
			self._tap_count = 0
		self._tap_count += 1
		self._last_tap_time = currentTime

		if self._pending_action:
			try:
				self._pending_action.Stop()
			except (AttributeError, RuntimeError):
				pass
			self._pending_action = None

		def execute_action():
			try:
				currentUrl = self.get_current_url()
				if self._tap_count == 1:
					nvdaGui.mainFrame.popupSettingsDialog(MainDialog, currentUrl, self.config)
					return
				if self._tap_count == 2:
					if not currentUrl:
						ui.message(_("Cannot capture URL. Make sure you are in a browser."))
						return
					nvdaGui.mainFrame.popupSettingsDialog(AddSiteDialog, self.config, currentUrl)
					return
				if self._tap_count >= 3:
					if not currentUrl:
						ui.message(_("Cannot capture URL. Make sure you are in a browser."))
						return
					existingSite = self.config.get_site_by_url(currentUrl)
					if not existingSite:
						ui.message(_("No site configured for the current page yet. Double-tap to add one first."))
						return
					nvdaGui.mainFrame.popupSettingsDialog(
						AddSiteDialog,
						self.config,
						edit_mode=True,
						site_id=existingSite["display_name"]
					)
			except (RuntimeError, ValueError) as err:
				log.error(f"BrowsersDictionary: Dialog error: {err}")
			finally:
				self._tap_count = 0
				self._pending_action = None

		self._pending_action = wx.CallLater(int(DOUBLE_TAP_THRESHOLD * 1000), execute_action)
