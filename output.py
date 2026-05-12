def _normalize_c_format(fmt):
    replacements = [
        ('%lld', '%d'),
        ('%llu', '%d'),
        ('%ld', '%d'),
        ('%li', '%d'),
        ('%lu', '%d'),
        ('%lf', '%f'),
        ('%i', '%d'),
        ('%u', '%d'),
    ]
    for source, target in replacements:
        fmt = fmt.replace(source, target)
    return fmt

def _coerce_c_printf_arg(value):
    if isinstance(value, list) and all(isinstance(ch, str) and len(ch) == 1 for ch in value):
        chars = []
        for ch in value:
            if ch == '\0':
                break
            chars.append(ch)
        return ''.join(chars)
    return value

def _c_printf(fmt, *args):
    fmt = _normalize_c_format(fmt)
    values = tuple(_coerce_c_printf_arg(arg) for arg in args)
    text = fmt % values if values else fmt
    print(text, end='')

def main():
    arr = ([1, 2, 3, 4, 5] + [0] * max(0, 5 - len([1, 2, 3, 4, 5])))[:5]
    sum = 0
    i = 0
    while (i < 5):
        sum += arr[i]
        i += 1
    _c_printf('sum = %d\n', sum)
    _c_printf('third element = %d\n', arr[2])
    return 0

if __name__ == "__main__":
    main()