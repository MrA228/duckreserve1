# Translation Setup Guide

This guide explains how to set up and use Russian language support in DuckReserve.

## Installation

1. Install Flask-Babel (already added to requirements.txt):
```bash
pip install Flask-Babel
```

## Compiling Translations

After creating or updating translation files, you need to compile them:

```bash
# Extract translatable strings from templates and Python files
pybabel extract -F babel.cfg -k _ -o messages.pot .

# Initialize or update translation files (only needed once per language)
pybabel init -i messages.pot -d translations -l ru

# Update existing translation files after adding new strings
pybabel update -i messages.pot -d translations

# Compile translation files to .mo format (required for Flask to use them)
pybabel compile -d translations
```

## Adding New Translations

1. Add translatable strings in templates using `{{ _("Your text here") }}`
2. Run `pybabel extract -F babel.cfg -k _ -o messages.pot .`
3. Run `pybabel update -i messages.pot -d translations`
4. Edit `translations/ru/LC_MESSAGES/messages.po` to add Russian translations
5. Run `pybabel compile -d translations`
6. Restart your Flask application

## Using Translations in Templates

Wrap any text you want to translate with the `_()` function:

```jinja2
{{ _("Welcome to DuckReserve") }}
```

For placeholders and variables:
```jinja2
{{ _("Hello, %(name)s!")|format(name=user.name) }}
```

## Language Switcher

The language switcher is already added to the navigation bar. Users can click the globe icon to switch between English and Russian.

## Current Status

- ✅ Flask-Babel configured
- ✅ Language switcher added to navbar
- ✅ Translation files created for Russian
- ⚠️ Translation files need to be compiled (run `pybabel compile -d translations`)
- ⚠️ Some templates still need translation strings added

## Next Steps

1. Compile the translation files using the commands above
2. Update remaining templates to use `{{ _("text") }}` for translatable strings
3. Add more translations to `translations/ru/LC_MESSAGES/messages.po` as needed

