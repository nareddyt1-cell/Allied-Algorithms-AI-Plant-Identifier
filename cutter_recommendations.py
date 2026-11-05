"""Prompt A content for the Allied Algorithms removal tool."""


def get_multiflora_rose_guidance() -> dict:
    return {
        "prompt": "PROMPT A",
        "title": "Multiflora Rose candidate detected",
        "message": (
            "The scan found a possible Multiflora Rose (Rosa multiflora). "
            "Review the identification before removing the plant."
        ),
        "tool": "Allied Algorithms specialized net-cutter",
        "recommendations": [
            "Confirm the plant identification using leaves, stems, flowers, and fruit.",
            "Wear gloves, eye protection, long sleeves, and sturdy footwear; stems may have thorns.",
            "Keep people and pets clear of the work area.",
            "Use the approved net-cutter according to its safety instructions and local guidance.",
            "Remove or manage regrowth as appropriate; check the site again during the growing season.",
            "Dispose of plant material according to local invasive-plant guidance; do not spread seeds or fragments.",
        ],
        "safety_note": (
            "This is general guidance, not a substitute for the tool manufacturer's "
            "instructions or advice from a qualified land manager."
        ),
    }
