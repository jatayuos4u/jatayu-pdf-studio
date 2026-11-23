"""Map between displayed page coordinates and PDF selection data."""
def page_words(page):
    return page.get_text("words", sort=True)


def nearest_word(words, point):
    def distance(index):
        x0, y0, x1, y1 = words[index][:4]
        dx = max(x0 - point.x, point.x - x1, 0)
        dy = max(y0 - point.y, point.y - y1, 0)
        return dx * dx + dy * dy

    return min(range(len(words)), key=distance)


def copy_text(words):
    parts = []
    previous = None
    for word in words:
        line = tuple(word[5:7])
        if previous is not None:
            parts.append(" " if previous == line else "\n")
        parts.append(word[4])
        previous = line
    return "".join(parts)

