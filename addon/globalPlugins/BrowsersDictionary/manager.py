# manager.py

import os
import json
import re
import shutil
import globalVars
import addonHandler
from logHandler import log

addonHandler.initTranslation()

WORD_VALUE = "value"
WORD_IS_REGEX = "is_regex"
WORD_REPLACEMENT = "replacement"

# Best-effort, non-exhaustive heuristic for common catastrophic-backtracking
# shapes such as (x+)+ or (x*)*. A pattern that does not match this is not
# guaranteed safe, and one that does match is not guaranteed to actually
# hang; this is used only to show the user a caution message before saving
# a regex entry, never to block saving outright. Kept as a pure function
# (no NVDA API calls) so it is independently pytest-able outside NVDA.
_NESTED_QUANTIFIER_HINT = re.compile(r'\([^()]*[+*][^()]*\)[+*]')


def looks_potentially_catastrophic(pattern):
	if not pattern:
		return False
	return bool(_NESTED_QUANTIFIER_HINT.search(pattern))


class BrowsersDictionaryConfig:
	"""Configuration manager for BrowsersDictionary addon with per-site JSON files"""

	def __init__(self):
		self.sites = {}
		self._site_files = {}
		self.config_dir = os.path.join(globalVars.appArgs.configPath, "ChaiChaimee", "BrowsersDictionary")
		self._ensure_config_dir()
		self._migrate_old_config()
		self._load_all_sites()

	def _ensure_config_dir(self):
		if not os.path.exists(self.config_dir):
			os.makedirs(self.config_dir)

	def _get_unique_backup_path(self, directory, filename):
		root, ext = os.path.splitext(filename)
		counter = 1
		path = os.path.join(directory, filename)
		while os.path.exists(path):
			path = os.path.join(directory, f"{root}_{counter}{ext}")
			counter += 1
		return path

	def _migrate_old_config(self):
		# Two-layer migration (Section 13): the current config_dir is checked
		# implicitly by each call below (a layout whose folder no longer
		# exists is simply skipped), and the known prior layouts are checked
		# newest-first so a user who has been through more than one rename/
		# convention change still migrates correctly in a single pass:
		#   1. "ChaiChaimee\invisible" - this add-on's immediately preceding
		#      name, before the rename to Browsers Dictionary.
		#   2. a flat "<configPath>\BrowsersDictionary" folder - an older,
		#      pre-vendor-folder layout from before the "ChaiChaimee" vendor
		#      segment was introduced.
		# Each layout is migrated by the same non-destructive merge routine,
		# and every step logs exactly which layout was detected so a future
		# log.txt review can confirm which migration path actually ran.
		legacy_layouts = (
			("previous add-on name 'invisible'", os.path.join(globalVars.appArgs.configPath, "ChaiChaimee", "invisible")),
			("pre-vendor-folder flat layout", os.path.join(globalVars.appArgs.configPath, "BrowsersDictionary")),
		)
		for layout_label, old_dir in legacy_layouts:
			self._migrate_from_legacy_dir(old_dir, layout_label)

	def _migrate_from_legacy_dir(self, old_dir, layout_label):
		if not os.path.isdir(old_dir) or old_dir == self.config_dir:
			return

		self._ensure_config_dir()
		copied_any = False

		for item in os.listdir(old_dir):
			src = os.path.join(old_dir, item)
			if not os.path.isfile(src):
				continue

			dst = os.path.join(self.config_dir, item)
			try:
				if not os.path.exists(dst):
					shutil.copy2(src, dst)
					copied_any = True
				else:
					backup_dst = self._get_unique_backup_path(self.config_dir, item)
					shutil.copy2(src, backup_dst)
					copied_any = True
					log.info(f"BrowsersDictionary addon: Existing file {item} kept; old copy from {layout_label} saved as {os.path.basename(backup_dst)}")
			except OSError as err:
				log.error(f"BrowsersDictionary addon: Failed to copy old config file {item} from {layout_label}: {err}")

		if copied_any:
			try:
				shutil.rmtree(old_dir)
				log.info(f"BrowsersDictionary addon: Old config folder ({layout_label}) migrated to new location.")
			except OSError as err:
				log.error(f"BrowsersDictionary addon: Failed to remove old config folder ({layout_label}): {err}")

	def _safe_filename(self, name):
		name = re.sub(r'[\\/*?:"<>|]', "_", name)
		if len(name) > 100:
			name = name[:100]
		return name + ".json"

	def _normalize_site_data(self, site_data):
		normalized_words = []
		for word_data in site_data.get("words", []):
			if isinstance(word_data, str):
				normalized_words.append({
					WORD_VALUE: word_data,
					WORD_IS_REGEX: False,
					WORD_REPLACEMENT: ""
				})
			elif isinstance(word_data, dict):
				value = word_data.get(WORD_VALUE)
				if not isinstance(value, str) or not value:
					continue
				if WORD_IS_REGEX not in word_data:
					word_data[WORD_IS_REGEX] = False
				if WORD_REPLACEMENT not in word_data:
					word_data[WORD_REPLACEMENT] = ""
				normalized_words.append(word_data)

		site_data["words"] = normalized_words
		if "mode" not in site_data:
			site_data["mode"] = "single"

	def _same_word(self, first, second):
		return (
			first.get(WORD_VALUE) == second.get(WORD_VALUE)
			and first.get(WORD_IS_REGEX) == second.get(WORD_IS_REGEX)
			and first.get(WORD_REPLACEMENT) == second.get(WORD_REPLACEMENT)
		)

	def _merge_site_words(self, existing_site, incoming_site):
		existing_words = existing_site.setdefault("words", [])
		for incoming_word in incoming_site.get("words", []):
			if not any(self._same_word(existing_word, incoming_word) for existing_word in existing_words):
				existing_words.append(incoming_word)
		existing_words.sort(key=lambda item: item.get(WORD_VALUE, "").lower())

	def _load_all_sites(self):
		self.sites = {}
		self._site_files = {}
		duplicate_files_to_remove = []

		try:
			if not os.path.exists(self.config_dir):
				return

			json_files = [
				item for item in os.listdir(self.config_dir)
				if item.endswith('.json')
			]
			json_files.sort()

			for filename in json_files:
				filepath = os.path.join(self.config_dir, filename)

				try:
					with open(filepath, 'r', encoding='utf-8') as config_file:
						site_data = json.load(config_file)

					if not isinstance(site_data, dict):
						log.warning(f"BrowsersDictionary addon: Skipping non-object config file {filename}")
						continue
					if "url" not in site_data or "display_name" not in site_data:
						log.warning(f"BrowsersDictionary addon: Skipping invalid site file {filename}")
						continue

					self._normalize_site_data(site_data)
					site_id = site_data["display_name"]

					if site_id in self.sites:
						self._merge_site_words(self.sites[site_id], site_data)
						duplicate_files_to_remove.append(filepath)
						log.warning(f"BrowsersDictionary addon: Duplicate site '{site_id}' found in {filename}; words merged.")
					else:
						self.sites[site_id] = site_data
						self._site_files[site_id] = filename

				except ValueError as err:
					log.error(f"BrowsersDictionary addon: Invalid JSON in {filename}: {err}")
				except OSError as err:
					log.error(f"BrowsersDictionary addon: Failed reading {filename}: {err}")

			for duplicate_path in duplicate_files_to_remove:
				try:
					if os.path.exists(duplicate_path):
						os.remove(duplicate_path)
						log.info(f"BrowsersDictionary addon: Removed duplicate config file {os.path.basename(duplicate_path)} after merging.")
				except OSError as err:
					log.error(f"BrowsersDictionary addon: Failed to remove duplicate config file {duplicate_path}: {err}")

		except OSError as err:
			log.error(f"BrowsersDictionary addon: Error reading config directory: {err}")

	def _save_site(self, site_id):
		if site_id not in self.sites:
			return False

		site_data = self.sites[site_id]
		filename = self._site_files.get(site_id)
		if not filename:
			filename = self._safe_filename(site_id)
			self._site_files[site_id] = filename

		filepath = os.path.join(self.config_dir, filename)
		try:
			with open(filepath, 'w', encoding='utf-8') as config_file:
				json.dump(site_data, config_file, ensure_ascii=False, indent=2)
			return True
		except OSError as err:
			log.error(f"BrowsersDictionary addon: Error saving site config {site_id}: {err}")
			return False
		except (TypeError, ValueError) as err:
			log.error(f"BrowsersDictionary addon: Invalid data while saving site {site_id}: {err}")
			return False

	def _delete_site_file(self, site_id):
		filename = self._site_files.pop(site_id, self._safe_filename(site_id))
		filepath = os.path.join(self.config_dir, filename)
		try:
			if os.path.exists(filepath):
				os.remove(filepath)
			return True
		except OSError as err:
			log.error(f"BrowsersDictionary addon: Error deleting site config {site_id}: {err}")
			return False

	def _extract_domain(self, url):
		if not url:
			return None
		try:
			if "://" in url:
				url = url.split("://", 1)[1]
			domain = url.split("/", 1)[0].split(":", 1)[0]
			return domain.lower()
		except (AttributeError, IndexError, TypeError):
			return None

	def _extract_base_domain(self, domain):
		if not domain:
			return None
		parts = domain.split('.')
		if len(parts) >= 2:
			return '.'.join(parts[-2:])
		return domain

	def get_site_by_url(self, url):
		if not url:
			return None

		domain = self._extract_domain(url)
		for site_data in self.sites.values():
			site_url = site_data.get("url", "")
			mode = site_data.get("mode", "single")

			if mode == "single" and url == site_url:
				return site_data
			elif mode == "whole":
				current_base = self._extract_base_domain(domain) if domain else None
				site_base = self._extract_base_domain(self._extract_domain(site_url))
				if current_base and site_base and current_base == site_base:
					return site_data
			elif mode == "prefix":
				norm_site_url = site_url.rstrip('/')
				if url.lower().startswith(norm_site_url.lower()):
					return site_data
			elif mode == "regex":
				try:
					if re.match(site_url, url):
						return site_data
				except re.error:
					continue

		return None

	def get_site_by_id(self, site_id):
		return self.sites.get(site_id)

	def add_site(self, url, display_name, mode="single"):
		if not url or not display_name:
			return False

		if display_name in self.sites:
			counter = 1
			while f"{display_name} ({counter})" in self.sites:
				counter += 1
			display_name = f"{display_name} ({counter})"

		site_data = {
			"url": url,
			"display_name": display_name,
			"mode": mode,
			"words": []
		}
		self.sites[display_name] = site_data
		self._site_files[display_name] = self._safe_filename(display_name)
		return self._save_site(display_name)

	def update_site(self, old_site_id, new_display_name=None, new_url=None, new_mode=None):
		if old_site_id not in self.sites:
			return False

		site_data = self.sites[old_site_id]
		old_display_name = site_data.get("display_name")
		old_url = site_data.get("url")
		old_mode = site_data.get("mode")
		old_filename = self._site_files.get(old_site_id, self._safe_filename(old_site_id))

		final_site_id = old_site_id
		display_changed = False
		new_filename = old_filename

		if new_display_name and new_display_name != old_site_id:
			if new_display_name in self.sites:
				return False
			final_site_id = new_display_name
			display_changed = True
			new_filename = self._safe_filename(new_display_name)

		if new_display_name:
			site_data["display_name"] = new_display_name
		if new_url is not None:
			site_data["url"] = new_url
		if new_mode is not None:
			site_data["mode"] = new_mode

		if display_changed:
			self.sites[final_site_id] = site_data
			del self.sites[old_site_id]
			self._site_files.pop(old_site_id, None)
			self._site_files[final_site_id] = new_filename

		if not self._save_site(final_site_id):
			if display_changed:
				if final_site_id in self.sites:
					del self.sites[final_site_id]
				self.sites[old_site_id] = site_data
				self._site_files.pop(final_site_id, None)
				self._site_files[old_site_id] = old_filename

			site_data["display_name"] = old_display_name
			site_data["url"] = old_url
			site_data["mode"] = old_mode
			return False

		if display_changed and old_filename != new_filename:
			old_filepath = os.path.join(self.config_dir, old_filename)
			try:
				if os.path.exists(old_filepath):
					os.remove(old_filepath)
			except OSError as err:
				log.error(f"BrowsersDictionary addon: Failed to remove old site file {old_filename}: {err}")

		return True

	def remove_site(self, site_id):
		if site_id in self.sites:
			if self._delete_site_file(site_id):
				del self.sites[site_id]
				return True
		return False

	def _get_display_word(self, word_data):
		value = word_data.get(WORD_VALUE, "")
		is_regex = word_data.get(WORD_IS_REGEX, False)
		replacement = word_data.get(WORD_REPLACEMENT, "")

		if is_regex:
			if replacement:
				return f"{value} -> {replacement} [{_('Regex')}]"
			return f"{value} [{_('Regex')}]"

		if replacement:
			return f"{value} -> {replacement}"
		return value

	def get_words_for_site(self, site_id):
		site_data = self.get_site_by_id(site_id)
		if site_data:
			return site_data.get("words", [])
		return []

	def add_word(self, site_id, word, is_regex, replacement=""):
		if site_id not in self.sites:
			raise ValueError(_("Site not found"))

		new_word_data = {
			WORD_VALUE: word,
			WORD_IS_REGEX: is_regex,
			WORD_REPLACEMENT: replacement
		}
		words_list = self.sites[site_id]["words"]

		if any(
			d[WORD_VALUE] == word and d[WORD_IS_REGEX] == is_regex
			for d in words_list
		):
			raise ValueError(_("This pattern/regex combination already exists"))

		words_list.append(new_word_data)
		words_list.sort(key=lambda x: x[WORD_VALUE].lower())

		if not self._save_site(site_id):
			raise ValueError(_("Failed to save configuration (permission or disk error)"))

		return True

	def update_word(self, site_id, old_word_data, new_word, new_is_regex, new_replacement=""):
		if site_id not in self.sites:
			raise ValueError(_("Site not found"))

		words_list = self.sites[site_id]["words"]
		index = -1
		for i, current_word in enumerate(words_list):
			if (
				current_word[WORD_VALUE] == old_word_data[WORD_VALUE]
				and current_word[WORD_IS_REGEX] == old_word_data[WORD_IS_REGEX]
			):
				index = i
				break

		if index == -1:
			raise ValueError(_("Original entry not found"))

		for i, current_word in enumerate(words_list):
			if i != index and current_word[WORD_VALUE] == new_word and current_word[WORD_IS_REGEX] == new_is_regex:
				raise ValueError(_("This pattern/regex combination already exists"))

		new_word_data = {
			WORD_VALUE: new_word,
			WORD_IS_REGEX: new_is_regex,
			WORD_REPLACEMENT: new_replacement
		}
		words_list[index] = new_word_data
		words_list.sort(key=lambda x: x[WORD_VALUE].lower())

		if not self._save_site(site_id):
			raise ValueError(_("Failed to save configuration (permission or disk error)"))

		return True

	def remove_word(self, site_id, word_data):
		if site_id not in self.sites:
			return False

		words_list = self.sites[site_id]["words"]
		try:
			words_list.remove(word_data)
			return self._save_site(site_id)
		except ValueError:
			log.error("BrowsersDictionary Config: Word data not found for removal.")
			return False

	def get_all_sites(self):
		result = []
		for site_id, site_data in self.sites.items():
			result.append((site_id, site_data.get("display_name", site_id)))
		result.sort(key=lambda item: item[1].lower())
		return result
