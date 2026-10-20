#!/bin/bash
# Refresh the big-driver-manager-cli catalog:
#   locale/big-driver-manager-cli.pot   strings of the command line
#   locale/<lang>.po                    merged with the new template
#   usr/share/locale/<lang>/LC_MESSAGES/big-driver-manager-cli.mo
#   the polkit policy's xml:lang messages
# Run from anywhere; needs gettext.
set -euo pipefail

cd "$(dirname "$0")/.."
domain=big-driver-manager-cli
core=usr/share/big-driver-manager-cli/core
policy=usr/share/polkit-1/actions/br.com.biglinux.drivermanager.cli.policy

xgettext --language=Python --from-code=UTF-8 \
    --keyword=_ --keyword=N_ --keyword=ngettext:1,2 \
    --add-comments=Translators --sort-by-file \
    --package-name="$domain" --msgid-bugs-address="https://github.com/biglinux/$domain" \
    --output="locale/$domain.pot" \
    usr/bin/big-driver-manager-cli \
    "$core/kernel_cli.py" "$core/gpu_cli.py" "$core/kernel_manager.py" \
    locale/extra_msgids.py

for po in locale/*.po; do
    lang=$(basename "$po" .po)
    msgmerge --quiet --update --backup=none --no-fuzzy-matching "$po" "locale/$domain.pot"
    mkdir -p "usr/share/locale/$lang/LC_MESSAGES"
    msgfmt --check --output-file="usr/share/locale/$lang/LC_MESSAGES/$domain.mo" "$po"
done

python3 -I - "$policy" locale <<'PY'
import gettext, re, sys
from pathlib import Path

policy, locale = Path(sys.argv[1]), Path(sys.argv[2])
text = policy.read_text(encoding="utf-8")
for tag in ("description", "message"):
    english = re.search(rf"  <{tag}>(.*?)</{tag}>\n", text).group(1)
    lines = [f"    <{tag}>{english}</{tag}>\n"]
    for po in sorted(locale.glob("*.po")):
        lang = po.stem
        mo = Path("usr/share/locale") / lang / "LC_MESSAGES" / "big-driver-manager-cli.mo"
        with mo.open("rb") as handle:
            translated = gettext.GNUTranslations(handle).gettext(english)
        if lang != "en" and translated != english:
            lines.append(f'    <{tag} xml:lang="{lang}">{translated}</{tag}>\n')
    text = re.sub(
        rf"(    <{tag}( xml:lang=\"[^\"]+\")?>.*?</{tag}>\n)+", "".join(lines), text, count=1
    )
policy.write_text(text, encoding="utf-8")
PY
echo "updated: locale/$domain.pot, $(ls locale/*.po | wc -l) catalogs, $policy"
