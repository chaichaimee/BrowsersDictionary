<p align="center">
  <img src="https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico" alt="NVDA Logo" width="120">
</p>

# Browsers Dictionary

<p align="center">Your personal pronunciation dictionary for every website, spoken exactly the way you want it.</p>

<p align="center">
  <b>author:</b> chai chaimee<br>
  <b>url:</b> https://github.com/chaichaimee/BrowsersDictionary
</p>

---

## Introduction

Browsers Dictionary lets you build a custom, per-website "pronunciation dictionary" for NVDA speech. If a site uses words, abbreviations, or jargon that NVDA reads awkwardly, you can define a text or regular-expression pattern and a replacement, and NVDA will speak your replacement instead whenever that pattern appears on that specific page, on that whole website, or on any URL matching your own pattern.

The add-on works automatically once set up: it silently watches which browser tab or page is active, and rewrites the speech NVDA is about to say in real time, based on the rules you configured for the current site.

> [!NOTE]
> **Upgrading from Invisible?**<br>
> Browsers Dictionary is an enhanced version of the "Invisible" add-on. If you currently have Invisible installed, simply uninstall it first, then install Browsers Dictionary and keep using it right away. You do not need to redo any of your site setups: all the site settings you previously configured in Invisible are automatically carried over into Browsers Dictionary the first time it runs.

---

### Hot Keys

> **NVDA+Shift+W**<br>
> Single Tap : Open Browsers Dictionary Settings for the current site<br>
> Double Tap : Capture the current page's URL and open the Add New Site dialog

Tap once to review or edit the dictionary entries already saved for the page you are currently on. Tap twice, quickly, while focused in your browser to immediately create a new site entry using the URL of the page you are currently viewing. If NVDA cannot detect a URL for a double tap (for example, you are not in a supported browser), it will tell you "Cannot capture URL. Make sure you are in a browser."

---

## Features

### Automatic, Live URL Tracking

Browsers Dictionary keeps track of the page you are on without you having to do anything. It updates its record of the current URL:

- When you switch to a browser window (Firefox, Chrome, Edge, Brave, Opera, or Internet Explorer)
- When a page finishes loading
- When focus moves to a new element, at most twice per second, so it stays current without overloading the browser

This URL is what the add-on uses behind the scenes to decide which set of dictionary entries applies to what you are currently reading.

### Per-Site Word and Pattern Replacement

For each site you add, you can create a list of entries. Each entry has:

- A **Pattern**: the exact text, or a regular expression, to look for
- An optional **Replacement**: what NVDA should say instead. If left blank, the matched text is simply removed from speech
- A **Use as regular expression** checkbox, for advanced pattern matching

Whenever NVDA is about to speak text on a matching page, Browsers Dictionary checks it against your list and substitutes matches before the speech is spoken. Plain-text entries are matched first (longest entries first, to avoid partial overlaps), followed by your regular expressions.

### Three Ways to Match a Site

When adding or editing a site, you choose how broadly its dictionary entries should apply:

- **Single page only**: entries apply only to the exact URL you saved.
- **Whole website (domain)**: entries apply to every page on the same domain, regardless of the specific path.
- **Regular expression**: entries apply to any URL that matches a pattern you write, checked from the start of the address.

### Managing Sites and Entries

The Settings dialog (opened with a single tap of NVDA+Shift+W) contains a Site List and, for the selected site, an Entries list. From here you can:

- **Add**, **Edit**, or **Remove** a word or pattern entry, with confirmation before removal
- Open a context menu (or press Delete) on a site or an entry for quick Edit/Remove actions
- **Edit Site** or **Remove Site** directly from the Site List's context menu
- Cancel an in-progress edit and return to adding new entries

Adding a new site opens a dedicated dialog where you set its display name, URL, and matching mode; saving a new site immediately reopens the main Settings dialog for that site so you can start adding entries right away.

### Import Entries from a File

You can bulk-load entries into the currently selected site using **Import from file...**. Browsers Dictionary reads a JSON file containing a "words" list, where each entry can be a plain string (treated as a simple text replacement) or a full object with pattern, replacement, and regex settings. After you confirm, it reports how many entries were added and how many were skipped, for example because they already existed for that site.

### Regex Safety Warnings and Time Budget

To protect you from patterns that could freeze or slow down speech:

- When you save a regular expression that looks like it could cause runaway "catastrophic backtracking" (certain nested repeating groups), NVDA warns you that the pattern may run slowly, so you can simplify it. This is a helpful caution, not a hard block; the entry is still saved
- While actually speaking, Browsers Dictionary allows only a brief total processing time for all regular-expression entries on a single piece of speech. If that budget runs out, any remaining regex entries for that piece of speech are skipped so your speech is not held up
- Extremely long stretches of text are not scanned for replacements at all, since scanning them would add delay without meaningful benefit

### Seamless Migration from Older Configurations

Browsers Dictionary automatically checks for configuration data left behind by earlier versions or the previous "Invisible" add-on name, and merges it into its current configuration the first time it runs. Sites and entries from an older layout are copied in without overwriting anything you have already set up; if a file with the same name already exists, the older copy is kept as a backup instead of being discarded. Duplicate site files that end up representing the same site are automatically merged, with duplicate entries combined into one list.

---

## Support Me

If this tool has made your life easier, consider fueling the next update with a small donation.

<p align="center">
  <a href="https://buy.stripe.com/dRm9AU1xQ3Ds22N6VK1VK01">
    <img src="https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe" alt="Support me">
  </a>
</p>

Your support means the world. Let's build something great together

&copy; 2026 Chai Chaimee NVDA Add-on Released under GNU GPL