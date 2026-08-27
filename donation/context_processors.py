from datetime import datetime
from .translations import ENGLISH_TRANSLATIONS, URDU_TRANSLATIONS

def ui_context(request):
    """Shared template variables for filters and UI."""
    current_year = datetime.now().year
    year_range = list(range(current_year + 1, current_year - 6, -1))
    
    lang = 'en'
    try:
        if hasattr(request, 'session') and request.session is not None:
            lang = request.session.get('lang', 'en')
    except Exception:
        lang = 'en'
    t_dict = URDU_TRANSLATIONS if lang == 'ur' else ENGLISH_TRANSLATIONS

    months = [
        (1, t_dict['january']), (2, t_dict['february']), (3, t_dict['march']), (4, t_dict['april']),
        (5, t_dict['may']), (6, t_dict['june']), (7, t_dict['july']), (8, t_dict['august']),
        (9, t_dict['september']), (10, t_dict['october']), (11, t_dict['november']), (12, t_dict['december']),
    ]

    return {
        'year_range': year_range,
        'months_list': months,
        'current_year': current_year,
        'current_month': datetime.now().month,
        'LANG': lang,
        'T': t_dict,
    }
