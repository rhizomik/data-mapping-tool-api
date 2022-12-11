import re

DICT_REGEXPS = {
    'date_yyyy_mm_dd': r"^\d{4}\-(0?[1-9]|1[012])\-(0?[1-9]|[12][0-9]|3[01])$",
    "ipv4": r"(?<![-\.\d])(?:0{0,2}?[0-9]\.|1\d?\d?\.|2[0-5]?[0-5]?\.){3}(?:0{0,2}?[0-9]|1\d?\d?|2[0-5]?[0-5]?)(?![\.\d])"
}


def __compare_parity(values, regex_string):
    list_of_values = list(values)
    for value in list_of_values:
        result = re.fullmatch(regex_string, value)
        if result is None:
            return False
    return True


def infere_sub_type(values):
    final_regexp = None
    for regex, regex_string in DICT_REGEXPS.items():
        result = __compare_parity(values, regex_string)
        if result:
            final_regexp = regex
    return final_regexp
