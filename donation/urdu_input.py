"""
Helpers for the "Roman Urdu in, approved Urdu out" form flow.

* The form shows an editable Urdu box next to every Roman Urdu text field
  (`<name>` -> `<name>_ur`).
* `ur_value()` reads what the user approved, `learn()` remembers corrections
  (so typing "ali" gives "علی" next time), and `ur_text()` is what the PDF uses.
"""
import re
import time

from . import translations
from .translations import translate_user_input_to_urdu

_CACHE = {'t': 0.0, 'map': {}}
_TTL = 30  # seconds


def _user_map():
    now = time.time()
    if now - _CACHE['t'] > _TTL:
        try:
            from .models import WordMapping
            _CACHE['map'] = {w.roman: w.urdu for w in WordMapping.objects.all()}
        except Exception:      # DB not migrated yet, etc.
            _CACHE['map'] = {}
        _CACHE['t'] = now
    return _CACHE['map']


def _invalidate():
    _CACHE['t'] = 0.0


translations.USER_MAP_PROVIDER = _user_map

_EDGE = re.compile(r'^[^\w]+|[^\w]+$')


def _clean(tok):
    return _EDGE.sub('', tok)


def learn(roman, urdu):
    """Remember word-level corrections (only when both texts have the same word count)."""
    rt, ut = roman.split(), urdu.split()
    auto = translate_user_input_to_urdu(roman).split()
    if not (len(rt) == len(ut) == len(auto)):
        return
    from .models import WordMapping
    changed = False
    for r, u, a in zip(rt, ut, auto):
        r, u, a = _clean(r).lower(), _clean(u), _clean(a)
        if not r or not u or u == a or not r.isascii() or r.isdigit():
            continue
        if any(ord(c) < 128 and c.isalpha() for c in u):   # urdu box still holds Roman letters
            continue
        WordMapping.objects.update_or_create(roman=r, defaults={'urdu': u})
        changed = True
    if changed:
        _invalidate()


def resolve(roman, urdu):
    """Final Urdu to store: what the user approved, else the engine's suggestion."""
    roman = (roman or '').strip()
    urdu = (urdu or '').strip()
    if not roman:
        return ''
    if not urdu:
        return translate_user_input_to_urdu(roman)
    try:
        learn(roman, urdu)
    except Exception:
        pass
    return urdu


def ur_value(request, name, roman, index=None):
    """Approved Urdu for form field `name` (single field or row `index` of `name[]`)."""
    if index is not None:
        lst = request.POST.getlist(name + '_ur[]') or request.POST.getlist(name + '_ur')
        posted = lst[index] if index < len(lst) else ''
    else:
        posted = request.POST.get(name + '_ur', '')
    return resolve(roman, posted)


def ur_text(obj, field, is_urdu):
    """Text for the PDF: stored Urdu when available (Urdu PDFs only), else the raw value."""
    raw = getattr(obj, field, '') or ''
    if is_urdu:
        return (getattr(obj, field + '_ur', '') or '').strip() or raw
    return raw


def composed_ur(prefix, note_roman, note_urdu, default_prefix=None):
    """Urdu for notes the views build as  "<prefix> (<user note>)"  (e.g. Qist/Installment (...))."""
    note_roman = (note_roman or '').strip()
    if not note_roman:
        return translate_user_input_to_urdu(default_prefix or prefix)
    return f"{translate_user_input_to_urdu(prefix)} ({resolve(note_roman, note_urdu)})"