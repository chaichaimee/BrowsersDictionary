import wx
import addonHandler
import ui
import gui as nvdaGui
import re
import os
import json
from logHandler import log
from .manager import BrowsersDictionaryConfig, WORD_VALUE, WORD_IS_REGEX, WORD_REPLACEMENT, looks_potentially_catastrophic

addonHandler.initTranslation()

class MainDialog(wx.Dialog):
	"""Main dialog for managing BrowsersDictionary entries (words) for sites."""

	def __init__(self, parent, current_url, config):
		super().__init__(
			parent,
			title=_("Browsers Dictionary Settings"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
		)
		self.current_url = current_url
		self.config = config
		self.current_site_id = None
		self.editing_word_data = None

		existing_site = self.config.get_site_by_url(current_url)
		if existing_site:
			self.current_site_id = existing_site["display_name"]
			self.site_data = existing_site
		else:
			display_name = self._create_display_name(current_url)
			self.site_data = {
				"url": current_url,
				"display_name": display_name,
				"mode": "single",
				"words": []
			}
			self.current_site_id = display_name

		self.words_data = self.config.get_words_for_site(self.current_site_id)

		self._initUI()
		self._bindEvents()
		self.Centre()
		wx.CallAfter(self.wordsList.SetFocus)

	def _create_display_name(self, url):
		try:
			domain = self.config._extract_domain(url)
			if domain:
				if domain.startswith("www."):
					domain = domain[4:]
				return domain.capitalize()
		except (AttributeError, TypeError, IndexError):
			pass
		if len(url) > 30:
			return url[:27] + "..."
		return url

	def _initUI(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		siteBox = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Site List"))
		self.siteList = wx.ListBox(self, style=wx.LB_SINGLE, size=(-1, 100))
		self._load_site_list()
		siteBox.Add(self.siteList, 1, wx.EXPAND | wx.ALL, 5)
		mainSizer.Add(siteBox, 1, wx.EXPAND | wx.ALL, 5)

		entriesBox = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Entries"))

		self.wordsList = wx.ListBox(self, style=wx.LB_SINGLE, size=(-1, 150))
		self._update_words_list()
		entriesBox.Add(self.wordsList, 1, wx.EXPAND | wx.ALL, 5)

		entriesBox.Add(wx.StaticText(self, label=_("Pattern:")), 0, wx.ALL, 5)
		self.wordCtrl = wx.TextCtrl(self)
		entriesBox.Add(self.wordCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)

		replacementSizer = wx.BoxSizer(wx.HORIZONTAL)
		replacementSizer.Add(wx.StaticText(self, label=_("Replacement:")), 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
		self.replacementCtrl = wx.TextCtrl(self)
		replacementSizer.Add(self.replacementCtrl, 1, wx.EXPAND)
		entriesBox.Add(replacementSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)

		self.regexCheck = wx.CheckBox(self, label=_("Use as regular expression"))
		entriesBox.Add(self.regexCheck, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)

		wordBtnSizer = wx.BoxSizer(wx.VERTICAL)
		self.addUpdateWordBtn = wx.Button(self, label=_("&Add"))
		self.editWordBtn = wx.Button(self, label=_("&Edit"))
		self.removeWordBtn = wx.Button(self, label=_("&Remove"))
		self.cancelEditBtn = wx.Button(self, label=_("&Cancel"))
		self.cancelEditBtn.Hide()

		wordBtnSizer.Add(self.addUpdateWordBtn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		wordBtnSizer.Add(self.editWordBtn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		wordBtnSizer.Add(self.removeWordBtn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		wordBtnSizer.Add(self.cancelEditBtn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

		entriesBox.Add(wordBtnSizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP | wx.BOTTOM, 5)

		mainSizer.Add(entriesBox, 2, wx.EXPAND | wx.ALL, 5)

		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.importBtn = wx.Button(self, label=_("&Import from file..."))
		self.okBtn = wx.Button(self, wx.ID_OK, label=_("&OK"))
		self.closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		btnSizer.Add(self.importBtn, 0, wx.ALL, 5)
		btnSizer.AddStretchSpacer()
		btnSizer.Add(self.okBtn, 0, wx.ALL, 5)
		btnSizer.Add(self.closeBtn, 0, wx.ALL, 5)
		mainSizer.Add(btnSizer, 0, wx.EXPAND | wx.ALL, 10)

		self.SetSizer(mainSizer)
		self.SetSize(600, 650)
		self._select_current_site()
		self._update_button_states()

	def _bindEvents(self):
		self.Bind(wx.EVT_LISTBOX, self._onSiteSelect, self.siteList)
		self.Bind(wx.EVT_BUTTON, self._onAddUpdateWord, self.addUpdateWordBtn)
		self.Bind(wx.EVT_BUTTON, self._onEditWord, self.editWordBtn)
		self.Bind(wx.EVT_BUTTON, self._onRemoveWord, self.removeWordBtn)
		self.Bind(wx.EVT_BUTTON, self._onCancelEdit, self.cancelEditBtn)
		self.Bind(wx.EVT_BUTTON, self._onImport, self.importBtn)
		self.Bind(wx.EVT_BUTTON, self._onOk, self.okBtn)
		self.Bind(wx.EVT_BUTTON, self._onClose, self.closeBtn)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		self.Bind(wx.EVT_TEXT, self._onWordTextChange, self.wordCtrl)
		self.Bind(wx.EVT_CHECKBOX, self._onRegexCheck, self.regexCheck)
		self.Bind(wx.EVT_LISTBOX, self._onWordListSelect, self.wordsList)

		self.siteList.Bind(wx.EVT_CONTEXT_MENU, self._onSiteListContextMenu)
		self.wordsList.Bind(wx.EVT_CONTEXT_MENU, self._onWordsListContextMenu)

		self.siteList.Bind(wx.EVT_CHAR_HOOK, self._onSiteListKeyDown)
		self.wordsList.Bind(wx.EVT_CHAR_HOOK, self._onWordsListKeyDown)

		self.SetEscapeId(self.closeBtn.GetId())

	def _onSiteListKeyDown(self, evt):
		key = evt.GetKeyCode()
		if key == wx.WXK_DELETE:
			index = self.siteList.GetSelection()
			if index != wx.NOT_FOUND:
				sites = self.config.get_all_sites()
				if index < len(sites):
					site_id = sites[index][0]
					self._onRemoveSite(evt, site_id)
		else:
			evt.Skip()

	def _onWordsListKeyDown(self, evt):
		key = evt.GetKeyCode()
		if key == wx.WXK_DELETE and self.wordsList.GetSelection() != wx.NOT_FOUND:
			self._onRemoveWord(evt)
		else:
			evt.Skip()

	def _load_site_list(self):
		sites = self.config.get_all_sites()
		self.siteList.Clear()
		for site_id, display_name in sites:
			self.siteList.Append(display_name)

	def _select_current_site(self):
		sites = self.config.get_all_sites()
		for i, (site_id, display_name) in enumerate(sites):
			if site_id == self.current_site_id:
				self.siteList.SetSelection(i)
				break
		else:
			self.siteList.Append(self.site_data["display_name"])
			self.siteList.SetSelection(self.siteList.GetCount() - 1)

	def _update_words_list(self):
		self.wordsList.Clear()
		self.word_data_map = {}
		for i, word_data in enumerate(self.words_data):
			# The list shows only the pattern (WORD_VALUE), never the full
			# "pattern -> replacement [Regex]" form _get_display_word builds.
			# With many entries left at a blank replacement, that fuller
			# form rendered as "pattern -> " with nothing after the arrow,
			# and rows without a replacement looked inconsistent next to
			# rows that had one - the more blank-replacement entries in a
			# site's list, the more confusing it got. Showing just the
			# pattern keeps every row in the list the same shape regardless
			# of whether a replacement is set. _get_display_word itself is
			# unchanged and still used for the richer "Editing entry: ..."
			# announcement, where the extra detail is still useful.
			display = word_data.get(WORD_VALUE, "")
			self.wordsList.Append(display)
			self.word_data_map[i] = word_data
		if self.wordsList.GetCount() > 0:
			self.wordsList.SetSelection(0)

	def _update_button_states(self):
		has_word_sel = self.wordsList.GetSelection() != wx.NOT_FOUND
		has_word_text = bool(self.wordCtrl.GetValue().strip())
		if self.editing_word_data:
			self.addUpdateWordBtn.SetLabel(_("&Update"))
			self.addUpdateWordBtn.Enable(has_word_text)
			self.editWordBtn.Enable(False)
			self.removeWordBtn.Enable(False)
			self.cancelEditBtn.Show()
		else:
			self.addUpdateWordBtn.SetLabel(_("&Add"))
			self.addUpdateWordBtn.Enable(has_word_text)
			self.editWordBtn.Enable(has_word_sel)
			self.removeWordBtn.Enable(has_word_sel)
			self.cancelEditBtn.Hide()
		self.Layout()

	def _cancel_edit_mode(self):
		self.editing_word_data = None
		self.wordCtrl.Clear()
		self.regexCheck.SetValue(False)
		self.replacementCtrl.Clear()
		self._update_button_states()

	def _onSiteSelect(self, evt):
		if self.editing_word_data:
			self._cancel_edit_mode()
		index = self.siteList.GetSelection()
		if index == wx.NOT_FOUND:
			return
		sites = self.config.get_all_sites()
		if index < len(sites):
			self.current_site_id = sites[index][0]
			site_data = self.config.get_site_by_id(self.current_site_id)
			if site_data:
				self.site_data = site_data
				self.words_data = self.config.get_words_for_site(self.current_site_id)
				self._update_words_list()
				self._cancel_edit_mode()
				self._update_button_states()

	def _onSiteListContextMenu(self, evt):
		index = self.siteList.GetSelection()
		if index == wx.NOT_FOUND:
			return
		sites = self.config.get_all_sites()
		if index >= len(sites):
			return
		site_id = sites[index][0]
		menu = wx.Menu()
		edit_id = wx.ID_ANY
		remove_id = wx.ID_ANY
		edit_item = menu.Append(edit_id, _("&Edit Site"))
		remove_item = menu.Append(remove_id, _("&Remove Site"))
		self.Bind(wx.EVT_MENU, lambda evt, sid=site_id: self._onEditSite(evt, sid), id=edit_id)
		self.Bind(wx.EVT_MENU, lambda evt, sid=site_id: self._onRemoveSite(evt, sid), id=remove_id)
		self.PopupMenu(menu)
		menu.Destroy()

	def _onEditSite(self, evt, site_id):
		dlg = None
		try:
			dlg = AddSiteDialog(self, self.config, edit_mode=True, site_id=site_id)
			# A custom wx.Dialog opened via ShowModal must be bracketed with
			# prePopup()/postPopup(); omitting this silently breaks
			# EVT_CHAR_HOOK, which for a blind user means the dialog can look
			# open but not actually respond to keyboard input (Section 5.4).
			nvdaGui.mainFrame.prePopup()
			try:
				result = dlg.ShowModal()
			finally:
				nvdaGui.mainFrame.postPopup()
			if result == wx.ID_OK:
				self._load_site_list()
				new_name = dlg.get_new_display_name()
				if new_name:
					for i, (sid, display) in enumerate(self.config.get_all_sites()):
						if display == new_name:
							self.siteList.SetSelection(i)
							self._onSiteSelect(None)
							break
		except (RuntimeError, ValueError) as e:
			log.exception("Error editing site")
			wx.MessageBox(str(e), _("Error"), wx.OK | wx.ICON_ERROR)
		finally:
			if dlg is not None:
				dlg.Destroy()

	def _onRemoveSite(self, evt, site_id):
		sites = self.config.get_all_sites()
		display_name = None
		for sid, display in sites:
			if sid == site_id:
				display_name = display
				break
		if not display_name:
			return
		dlg = wx.MessageDialog(self,
			_("Are you sure you want to remove '{}'?").format(display_name),
			_("Confirm Removal"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
		)
		# Same prePopup()/postPopup() bracketing as _onEditSite (Section 5.4):
		# without it, Windows' foreground-lock heuristic can leave this
		# confirmation dialog visually present but unresponsive to keyboard
		# input, with no visual cue for a blind user that it happened.
		nvdaGui.mainFrame.prePopup()
		try:
			result = dlg.ShowModal()
		finally:
			nvdaGui.mainFrame.postPopup()
		if result == wx.ID_YES:
			if self.config.remove_site(site_id):
				self._load_site_list()
				if self.siteList.GetCount() > 0:
					self.siteList.SetSelection(0)
					self._onSiteSelect(None)
				else:
					self.current_site_id = None
					display_name = self._create_display_name(self.current_url)
					self.site_data = {
						"url": self.current_url,
						"display_name": display_name,
						"mode": "single",
						"words": []
					}
					self.current_site_id = display_name
					self.words_data = []
					self._update_words_list()
				ui.message(_("Site removed: {}").format(display_name))
			else:
				ui.message(_("Failed to remove site"))
		dlg.Destroy()

	def _onImport(self, evt):
		if not self.current_site_id:
			ui.message(_("Please select a site first."))
			return

		with wx.FileDialog(
			self,
			message=_("Select a JSON file to import"),
			wildcard="JSON files (*.json)|*.json",
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
		) as fileDialog:
			if fileDialog.ShowModal() == wx.ID_CANCEL:
				return
			path = fileDialog.GetPath()

		try:
			with open(path, 'r', encoding='utf-8') as f:
				data = json.load(f)
		except (OSError, ValueError) as e:
			wx.MessageBox(_("Could not read file: {}").format(str(e)), _("Error"), wx.OK | wx.ICON_ERROR)
			return

		if not isinstance(data, dict) or "words" not in data:
			wx.MessageBox(_("The selected file does not appear to be a valid Browsers Dictionary site configuration."), _("Error"), wx.OK | wx.ICON_ERROR)
			return

		words_to_add = []
		for item in data["words"]:
			if isinstance(item, str):
				words_to_add.append({WORD_VALUE: item, WORD_IS_REGEX: False, WORD_REPLACEMENT: ""})
			elif isinstance(item, dict):
				# A dict entry missing the "value" key (malformed/hand-edited
				# import file) must be skipped here, not passed through - the
				# add loop below used to index word_data[WORD_VALUE] directly,
				# which raised an uncaught KeyError on such an entry and left
				# the whole import silently failing with no message a blind
				# user could act on.
				value = item.get(WORD_VALUE)
				if not isinstance(value, str) or not value:
					continue
				if WORD_IS_REGEX not in item:
					item[WORD_IS_REGEX] = False
				if WORD_REPLACEMENT not in item:
					item[WORD_REPLACEMENT] = ""
				words_to_add.append(item)

		if not words_to_add:
			wx.MessageBox(_("No valid word entries found in the file."), _("Information"), wx.OK | wx.ICON_INFORMATION)
			return

		confirmMsg = _("Import {} word(s) into the current site '{}'?").format(
			len(words_to_add), self.site_data.get("display_name", self.current_site_id)
		)
		if wx.MessageBox(confirmMsg, _("Confirm Import"), wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
			return

		added = 0
		skipped = 0
		caution_needed = False
		for word_data in words_to_add:
			value = word_data[WORD_VALUE]
			is_regex = word_data.get(WORD_IS_REGEX, False)
			# Imported regex entries must pass the same two-part safety gate
			# as a manually-typed one (Section 5.17): reject anything that
			# doesn't even compile, and flag - without blocking - anything
			# that matches the known catastrophic-backtracking shape. Without
			# this, importing a file was the one path that let a broken or
			# dangerous pattern into the dictionary unchecked.
			if is_regex:
				try:
					re.compile(value)
				except re.error as err:
					skipped += 1
					log.debug(f"Skipped invalid regex during import: {value[:50]} - {err}")
					continue
				if looks_potentially_catastrophic(value):
					caution_needed = True
			try:
				self.config.add_word(
					self.current_site_id,
					value,
					is_regex,
					word_data.get(WORD_REPLACEMENT, "")
				)
				added += 1
			except ValueError as e:
				skipped += 1
				log.debug("Skipped word during import: {}".format(str(e)))

		self.words_data = self.config.get_words_for_site(self.current_site_id)
		self._update_words_list()
		ui.message(_("Import completed: {} added, {} skipped.").format(added, skipped))
		if caution_needed:
			ui.message(_("Warning: one or more imported patterns may run slowly or freeze speech on long text. Review them in the Entries list."))

	def _onWordsListContextMenu(self, evt):
		if self.wordsList.GetSelection() == wx.NOT_FOUND:
			return
		menu = wx.Menu()
		edit_item = menu.Append(wx.ID_EDIT, _("&Edit Word"))
		remove_item = menu.Append(wx.ID_DELETE, _("&Remove Word"))
		self.Bind(wx.EVT_MENU, self._onEditWord, edit_item)
		self.Bind(wx.EVT_MENU, self._onRemoveWord, remove_item)
		self.PopupMenu(menu)
		menu.Destroy()

	def _onWordTextChange(self, evt):
		self._update_button_states()
		evt.Skip()

	def _onRegexCheck(self, evt):
		self._update_button_states()
		evt.Skip()

	def _onWordListSelect(self, evt):
		if self.editing_word_data:
			self._cancel_edit_mode()
		self._update_button_states()
		evt.Skip()

	def _onAddUpdateWord(self, evt):
		word = self.wordCtrl.GetValue().strip()
		is_regex = self.regexCheck.GetValue()
		replacement = self.replacementCtrl.GetValue().strip()
		if not word:
			ui.message(_("Please enter a pattern"))
			return
		if not self.current_site_id:
			ui.message(_("No site selected"))
			return
		if is_regex:
			try:
				re.compile(word)
			except re.error as e:
				ui.message(_("Invalid Regular Expression: {}").format(str(e)))
				return

		try:
			if self.editing_word_data:
				self.config.update_word(
					self.current_site_id,
					self.editing_word_data,
					word,
					is_regex,
					replacement
				)
				self.words_data = self.config.get_words_for_site(self.current_site_id)
				self._update_words_list()
				self._cancel_edit_mode()
				ui.message(_("Entry updated successfully"))
				wx.CallAfter(self.wordsList.SetFocus)
			else:
				self.config.add_word(self.current_site_id, word, is_regex, replacement)
				self.words_data = self.config.get_words_for_site(self.current_site_id)
				self._update_words_list()
				self.wordCtrl.Clear()
				self.regexCheck.SetValue(False)
				self.replacementCtrl.Clear()
				self._update_button_states()
				ui.message(_("Entry added successfully"))
				wx.CallAfter(self.wordCtrl.SetFocus)
			# Best-effort caution only; never blocks a save, since the
			# heuristic is not a reliable safety verdict either way.
			if is_regex and looks_potentially_catastrophic(word):
				ui.message(_("Warning: this pattern may run slowly or freeze speech on long text. Consider simplifying it."))
		except ValueError as e:
			ui.message(str(e))

	def _onEditWord(self, evt):
		index = self.wordsList.GetSelection()
		if index == wx.NOT_FOUND:
			return
		word_data = self.word_data_map.get(index)
		if not word_data:
			return
		self.wordCtrl.SetValue(word_data[WORD_VALUE])
		self.regexCheck.SetValue(word_data.get(WORD_IS_REGEX, False))
		self.replacementCtrl.SetValue(word_data.get(WORD_REPLACEMENT, ""))
		self.wordCtrl.SetFocus()
		self.editing_word_data = word_data
		self._update_button_states()
		ui.message(_("Editing entry: {}").format(self.config._get_display_word(word_data)))

	def _onCancelEdit(self, evt):
		self._cancel_edit_mode()
		ui.message(_("Edit cancelled"))
		wx.CallAfter(self.wordsList.SetFocus)

	def _onRemoveWord(self, evt):
		index = self.wordsList.GetSelection()
		if index == wx.NOT_FOUND:
			return
		word_data = self.word_data_map.get(index)
		if not word_data:
			return
		display = self.wordsList.GetString(index)
		dlg = wx.MessageDialog(self,
			_("Are you sure you want to remove '{}'?").format(display),
			_("Confirm Removal"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
		)
		# See _onRemoveSite: same prePopup()/postPopup() bracketing fix,
		# Section 5.4.
		nvdaGui.mainFrame.prePopup()
		try:
			result = dlg.ShowModal()
		finally:
			nvdaGui.mainFrame.postPopup()
		if result == wx.ID_YES:
			if self.config.remove_word(self.current_site_id, word_data):
				self.words_data = self.config.get_words_for_site(self.current_site_id)
				self._update_words_list()
				self._cancel_edit_mode()
				ui.message(_("Entry removed: {}").format(display))
				wx.CallAfter(self.wordsList.SetFocus)
			else:
				ui.message(_("Failed to remove entry"))
		dlg.Destroy()

	def _onOk(self, evt):
		self.EndModal(wx.ID_OK)

	def _onClose(self, evt):
		self.EndModal(wx.ID_CANCEL)


class AddSiteDialog(wx.Dialog):
	"""Dialog for adding a new site or editing an existing site."""

	def __init__(self, parent, config, current_url=None, edit_mode=False, site_id=None):
		title = _("Edit Site") if edit_mode else _("Add New Site")
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.config = config
		self.edit_mode = edit_mode
		self.site_id = site_id
		self.current_url = current_url
		self.new_display_name = None

		self._initUI()
		self._bindEvents()
		self._populate_modes()

		if edit_mode and site_id:
			self._load_site_data()
		else:
			self._set_defaults()

		self.Centre()
		wx.CallAfter(self.nameCtrl.SetFocus)

	def _initUI(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		nameSizer = wx.BoxSizer(wx.HORIZONTAL)
		nameSizer.Add(wx.StaticText(self, label=_("Display name:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		self.nameCtrl = wx.TextCtrl(self)
		nameSizer.Add(self.nameCtrl, 1, wx.EXPAND)
		mainSizer.Add(nameSizer, 0, wx.EXPAND | wx.ALL, 5)

		urlSizer = wx.BoxSizer(wx.HORIZONTAL)
		urlSizer.Add(wx.StaticText(self, label=_("URL:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		self.urlCtrl = wx.TextCtrl(self)
		urlSizer.Add(self.urlCtrl, 1, wx.EXPAND)
		mainSizer.Add(urlSizer, 0, wx.EXPAND | wx.ALL, 5)

		modeSizer = wx.BoxSizer(wx.HORIZONTAL)
		modeSizer.Add(wx.StaticText(self, label=_("Apply to:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		self.modeCombo = wx.ComboBox(
			self,
			choices=[
				_("Single page only"),
				_("Whole website (domain)"),
				_("Regular expression (match URL from start)")
			],
			style=wx.CB_READONLY
		)
		modeSizer.Add(self.modeCombo, 1, wx.EXPAND)
		mainSizer.Add(modeSizer, 0, wx.EXPAND | wx.ALL, 5)

		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.saveBtn = wx.Button(self, wx.ID_OK, label=_("&Save"))
		self.cancelBtn = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
		btnSizer.Add(self.saveBtn, 0, wx.RIGHT, 5)
		btnSizer.Add(self.cancelBtn, 0)
		mainSizer.Add(btnSizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

		self.SetSizer(mainSizer)
		self.SetMinSize((500, -1))
		self.Fit()

	def _bindEvents(self):
		self.saveBtn.Bind(wx.EVT_BUTTON, self._onSave)
		self.Bind(wx.EVT_CHAR_HOOK, self._onCharHook)

	def _populate_modes(self):
		self.modeCombo.SetSelection(0)

	def _set_defaults(self):
		if self.current_url:
			self.urlCtrl.SetValue(self.current_url)
			try:
				domain = self.config._extract_domain(self.current_url)
				if domain:
					if domain.startswith("www."):
						domain = domain[4:]
					self.nameCtrl.SetValue(domain.capitalize())
				else:
					self.nameCtrl.SetValue(self.current_url[:30])
			except (AttributeError, TypeError, IndexError):
				self.nameCtrl.SetValue(self.current_url[:30])

	def _load_site_data(self):
		site_data = self.config.get_site_by_id(self.site_id)
		if site_data:
			self.nameCtrl.SetValue(site_data.get("display_name", ""))
			self.urlCtrl.SetValue(site_data.get("url", ""))
			mode = site_data.get("mode", "single")
			if mode == "single":
				self.modeCombo.SetSelection(0)
			elif mode == "whole":
				self.modeCombo.SetSelection(1)
			elif mode == "regex":
				self.modeCombo.SetSelection(2)
			else:
				self.modeCombo.SetSelection(1)

	def get_new_display_name(self):
		return self.new_display_name

	def _onSave(self, evt):
		display_name = self.nameCtrl.GetValue().strip()
		url = self.urlCtrl.GetValue().strip()
		sel = self.modeCombo.GetSelection()
		if sel == 0:
			mode = "single"
		elif sel == 1:
			mode = "whole"
		else:
			mode = "regex"

		if not display_name:
			wx.MessageBox(_("Display name cannot be empty."), _("Error"), wx.OK | wx.ICON_ERROR)
			return
		if not url:
			wx.MessageBox(_("URL cannot be empty."), _("Error"), wx.OK | wx.ICON_ERROR)
			return

		# A "regex" mode site pattern is evaluated by get_site_by_url() on
		# every spoken utterance while a tracked browser is focused (via
		# _onFilterSpeechSequence), unlike a word-level pattern which only
		# runs against the current utterance's text. An invalid or
		# catastrophic-backtracking site pattern is therefore a repeating
		# main-thread hang risk, not a one-off - the same two-part gate
		# already used for word patterns (Section 5.17) must apply here too.
		if mode == "regex":
			try:
				re.compile(url)
			except re.error as e:
				wx.MessageBox(_("Invalid Regular Expression: {}").format(str(e)), _("Error"), wx.OK | wx.ICON_ERROR)
				return

		if self.edit_mode:
			if self.config.update_site(self.site_id, display_name, url, mode):
				self.new_display_name = display_name
				if mode == "regex" and looks_potentially_catastrophic(url):
					ui.message(_("Warning: this pattern may run slowly or freeze speech when matching URLs. Consider simplifying it."))
				self.EndModal(wx.ID_OK)
			else:
				wx.MessageBox(_("Failed to update site. The display name might already exist."), _("Error"), wx.OK | wx.ICON_ERROR)
		else:
			if self.config.add_site(url, display_name, mode):
				self.new_display_name = display_name
				if mode == "regex" and looks_potentially_catastrophic(url):
					ui.message(_("Warning: this pattern may run slowly or freeze speech when matching URLs. Consider simplifying it."))
				self.EndModal(wx.ID_OK)
				nvdaGui.mainFrame.popupSettingsDialog(MainDialog, url, self.config)
			else:
				wx.MessageBox(_("Failed to add site. It may already exist."), _("Error"), wx.OK | wx.ICON_ERROR)

	def _onCharHook(self, evt):
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CANCEL)
		else:
			evt.Skip()
