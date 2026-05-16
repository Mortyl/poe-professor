"""Debug: print all strings around the name/account boundary in the day-1 search binary."""
import urllib.request
import urllib.parse
import json
import gzip
import re

snapshot      = "0039-20260516-08939"
snapshot_name = "fate-of-the-vaal"
skill         = "Lightning Arrow"
ascendancy    = "Deadeye"

skill_enc = urllib.parse.quote(skill)
url = (
    f"https://poe.ninja/poe2/api/builds/{snapshot}/search"
    f"?overview={snapshot_name}&skill={skill_enc}&class={ascendancy}"
    f"&timeMachine=day-1"
)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
with urllib.request.urlopen(req, timeout=15) as r:
    raw = r.read()
try:
    raw = gzip.decompress(raw)
except Exception:
    pass

def extract_strings(data: bytes, min_len: int) -> list[str]:
    pattern = re.compile(
        rb"(?:[\x20-\x7e]"
        rb"|[\xc2-\xdf][\x80-\xbf]"
        rb"|[\xe0-\xef][\x80-\xbf]{2}"
        rb"|[\xf0-\xf4][\x80-\xbf]{3}"
        rb"){" + str(min_len).encode() + rb",}"
    )
    out = []
    for m in pattern.finditer(data):
        try:
            out.append(m.group().decode("utf-8"))
        except UnicodeDecodeError:
            out.append(m.group().decode("ascii", errors="replace"))
    return out

name_pos    = raw.find(b"name")
account_pos = raw.find(b"account", name_pos + 1)
name_block    = raw[name_pos + 4 : account_pos]
account_block = raw[account_pos + 7 :]

char_names    = [n.rstrip("*") for n in extract_strings(name_block, 1)
                 if n.rstrip("*") not in ("name", "account")]
account_names = extract_strings(account_block, 4)

schema_fields = {"class", "skills", "level", "life", "keypassives", "items", "mana"}
account_names = [a.rstrip("*") for a in account_names
                 if a.rstrip("*") not in schema_fields]

print(f"Char names: {len(char_names)}, Accounts: {len(account_names)}\n")
print(f"{'idx':>4}  {'char name':<35}  {'paired account'}")
print("-" * 75)
for i, (char, acct) in enumerate(zip(char_names, account_names)):
    marker = " <<<<" if "Shlomo" in char else ""
    print(f"{i:>4}  {char:<35}  {acct}{marker}")
    if i > 20:
        print("  ...")
        break
