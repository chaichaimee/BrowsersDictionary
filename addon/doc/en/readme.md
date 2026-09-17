<div align="center">

<img src="https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico" alt="NVDA Logo" width="120">

# Browsers Dictionary

Your own speech dictionary for every website — hear pages the way you want to hear them.

**author:** chai chaimee  
**url:** [https://github.com/chaichaimee/BrowsersDictionary](https://github.com/chaichaimee/BrowsersDictionary)

</div>

---

## Introduction

Browsers Dictionary lets you build your own **per-website speech dictionary** for NVDA. Unlike NVDA's built-in speech dictionary, which applies everywhere, this add-on lets you attach word and phrase substitutions to specific sites only — so a rule you create for one website never leaks into another website, or into any other application.

You can rename confusing labels, shorten long or repetitive text, or silence phrases you never want spoken, all scoped to just the page or site where they bother you. Rules apply live as you browse, and can be built from either plain text matches or regular expressions.

Supported browsers: **Firefox, Chrome, Microsoft Edge, Brave, Opera,** and **Internet Explorer**.

> [!NOTE]
> This add-on works entirely offline. It does not send or fetch any data over the network — all dictionaries are stored locally on your computer.

---

## Hot Keys

> **Alt+Windows+B**  
> **Single Tap :** Open Browsers Dictionary Settings for the current site  
> **Double Tap :** Add the current page as a new site  
> **Triple Tap :** Edit the current site's existing configuration

**How tapping works:** Tap the key combination once, twice, or three times in quick succession (within a fraction of a second of each other). Waiting slightly longer between presses restarts the count, so a single slow press is always treated as a single tap.

**Single tap** always opens the main Settings dialog, showing the site matching your current page if one is already configured, or a ready-to-fill new entry if not.

**Double tap** is a shortcut to quickly register the page you are currently on as a new site. It requires NVDA to have successfully captured the page's URL first; if it hasn't, you'll hear a message asking you to make sure you're in a browser.

**Triple tap** jumps straight to editing the site already configured for your current page. If no site is configured yet for that page, you'll be told to double-tap first to add one.

---

## Features

### Per-Site Speech Dictionaries

Each site you add gets its own independent list of word/phrase entries. An entry can either be:

**A plain text replacement** — any exact occurrence of the pattern is swapped for your replacement text.  
**A regular expression replacement** — for more flexible, pattern-based matching.

Leaving the replacement field blank is a valid, deliberate choice — it means "speak nothing" for that pattern, exactly like leaving a replacement blank in NVDA's own built-in speech dictionary.

*Example:* On a site where a chat button is announced as "btn_send_msg_42", you could add a plain text entry replacing it with "Send".

### Three Ways to Match a Site

When adding or editing a site, you choose how its address is matched against the page you're on:

**Single page only** — the dictionary applies only when the URL is an exact match. Best for a page whose address never changes.  
**Whole website (domain)** — the dictionary applies anywhere on the same domain, regardless of the rest of the address. This is the default and recommended choice, since most sites use unique per-page or per-session addresses.  
**Regular expression** — the dictionary applies to any URL that matches your pattern from the start. Useful for sites with a predictable URL structure you want to target precisely.

### Automatic Current-Site Detection

Browsers Dictionary keeps track of the address of the page you're currently viewing in the background, so it always knows which site's dictionary — if any — should apply. This tracking updates:

- When you switch to a browser window.
- When focus moves within the page (checked no more than twice a second, to avoid unnecessary work).
- The moment a new page finishes loading.

You never need to do anything to trigger this — it happens automatically as you browse.

### Matching Across Split Speech

NVDA sometimes announces a single line as several separate pieces of speech — for example, a link's role, the link's own text, and the text that follows it. Browsers Dictionary is designed to catch patterns that span exactly this kind of boundary, so a phrase like "messages until ..." can still be matched and replaced even when "messages" is a link's text and the rest follows immediately after it.

Very long spoken passages (over 20,000 characters) are skipped from scanning entirely, since matching such large chunks adds noticeable cost for essentially no realistic benefit.

### Regular Expression Safety Checks

Whenever you save a regular expression — whether for a word entry or for a site's own URL pattern — Browsers Dictionary checks it in two ways:

**Step 1 — Validity check:** the pattern must actually compile as a valid regular expression, or saving is refused with an explanation.  
**Step 2 — Runaway pattern check:** the pattern is compared against a known "shape" that commonly causes regular expressions to run extremely slowly on certain text (repeated nested groups such as `(x+)+`). If it matches this shape, you'll hear a caution message — but the pattern is still saved, since this check cannot guarantee a pattern is actually unsafe, only that it resembles ones that can be.

> [!NOTE]
> As an extra safeguard while you browse, all the regex word entries for a single spoken phrase share a combined time budget of 0.1 seconds. If that budget runs out, any remaining regex entries for that phrase are skipped for that occurrence, so one heavy pattern cannot noticeably delay your speech.

### Managing Sites and Entries

The Settings dialog lists all your configured sites on one side and the current site's dictionary entries on the other. From here you can:

- Add, edit, or remove a dictionary entry (also reachable via the Delete key or a right-click context menu on the entries list).
- Edit or remove an entire site (also reachable via the Delete key or a right-click context menu on the site list).
- Import a list of entries from a JSON file directly into the currently selected site.

### Importing Entries From a File

You can bulk-load dictionary entries into the currently selected site from a JSON file. The file needs a "words" list containing either plain text values or fuller entries with a pattern, an optional regex flag, and an optional replacement.

Malformed entries are skipped rather than stopping the whole import, and you're told exactly how many entries were added versus skipped once it finishes. Imported regular expressions go through the same validity and runaway-pattern checks described above.

### Automatic Configuration Migration

If Browsers Dictionary detects dictionaries saved by an older version of the add-on (including one released under this add-on's previous name), it automatically copies them into the current configuration location the first time it starts. Nothing is lost even if entries already exist in both places — matching sites have their word lists merged together instead of one copy overwriting the other.

---

## Support Me

If this tool has made your life easier, consider fueling the next update with a small donation.

<p align="center">
  <a href="https://buy.stripe.com/dRm9AU1xQ3Ds22N6VK1VK01">
    <img src="https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe" alt="Support me">
  </a>
</p>

Your support means the world. Let's build something great together.

<p align="center">
  <sub>&copy; 2026 Chai Chaimee NVDA Add-on Released under GNU GPL</sub>
</p>