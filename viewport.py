"""Compute PDF display scale from the available viewport."""

PIXELS_PER_POINT = 96 / 72
PAGE_MARGIN = 10
MAX_RENDER_DIMENSION = 4096


def display_scale(page_width, page_height, viewport_width, viewport_height, zoom):
    # Reserve one pixel for the rasterizer's outward rounding.
    available_width = max(1, viewport_width - 2 * PAGE_MARGIN - 1)
    available_height = max(1, viewport_height - 2 * PAGE_MARGIN - 1)
    if zoom == "Fit page":
        scale = min(available_width / page_width, available_height / page_height)
    elif zoom == "Fit width":
        scale = available_width / page_width
    else:
        scale = float(zoom.rstrip("%")) / 100 * PIXELS_PER_POINT
    return min(scale, MAX_RENDER_DIMENSION / max(page_width, page_height))
