"""Small helpers shared by the command-line entry points."""


def print_table(title: str, header: tuple[str, ...], rows: list[tuple]) -> None:
    print(f"\n== {title}")
    if not rows:
        print("(none)")
        return
    cells = [tuple(str(c) for c in r) for r in [header, *rows]]
    widths = [max(len(r[i]) for r in cells) for i in range(len(header))]
    for r in cells:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip())
