
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import html
from datetime import datetime, timezone

USERNAME = os.environ.get("GH_USERNAME", "").strip()
TOKEN = os.environ.get("GH_TOKEN", "").strip()
OUTPUT = "skill-radar.svg"

if not USERNAME:
    raise SystemExit("Set GH_USERNAME to your GitHub username.")

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "skill-radar-generator",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def get_json(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_all_languages():
    totals = {}
    page = 1

    while True:
        url = (
            f"{API}/users/{urllib.parse.quote(USERNAME)}/repos"
            f"?type=owner&sort=updated&per_page=100&page={page}"
        )
        repos = get_json(url)

        if not repos:
            break

        for repo in repos:
            if repo.get("fork") or repo.get("archived"):
                continue

            languages_url = repo.get("languages_url")
            if not languages_url:
                continue

            try:
                languages = get_json(languages_url)
            except (urllib.error.HTTPError, urllib.error.URLError) as error:
                print(f"Skipping {repo.get('name')}: {error}")
                continue

            for language, byte_count in languages.items():
                totals[language] = totals.get(language, 0) + byte_count

        if len(repos) < 100:
            break
        page += 1

    return totals


def make_svg(totals):
    width, height = 760, 540
    cx, cy, radius = 380, 218, 120
    languages = sorted(
        totals.items(), key=lambda item: item[1], reverse=True
    )[:8]
    total_bytes = sum(totals.values())

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="760" height="540" viewBox="0 0 760 540" '
        'role="img" aria-labelledby="title desc">',
        '<title id="title">GitHub Language Radar</title>',
        '<desc id="desc">Language distribution from public repositories.</desc>',
        '<rect width="760" height="540" rx="20" fill="#0d1117"/>',
        '<text x="380" y="38" fill="#f0f6fc" text-anchor="middle" '
        'font-family="Arial,sans-serif" font-size="23" '
        'font-weight="700">GITHUB LANGUAGE RADAR</text>',
        '<text x="380" y="62" fill="#8b949e" text-anchor="middle" '
        'font-family="Arial,sans-serif" font-size="12">'
        + html.escape(USERNAME.upper())
        + ' · ACTUAL PUBLIC REPOSITORY CODE</text>',
    ]

    if not languages or total_bytes == 0:
        parts.extend([
            '<text x="380" y="210" fill="#36bcf7" text-anchor="middle" '
            'font-family="Arial,sans-serif" font-size="20">'
            'No language data yet</text>',
            '<text x="380" y="245" fill="#c9d1d9" text-anchor="middle" '
            'font-family="Arial,sans-serif" font-size="14">'
            'Create a public repository and push some code.</text>',
            '<text x="380" y="275" fill="#8b949e" text-anchor="middle" '
            'font-family="Arial,sans-serif" font-size="12">'
            'This chart does not invent skill percentages.</text>',
        ])
    else:
        count = len(languages)

        def point(index, distance):
            import math
            angle = -math.pi / 2 + index * 2 * math.pi / count
            return (
                cx + math.cos(angle) * distance,
                cy + math.sin(angle) * distance,
            )

        def polygon(distance):
            return " ".join(
                f"{x:.2f},{y:.2f}"
                for x, y in (point(i, distance) for i in range(count))
            )

        parts.append(
            '<g fill="none" stroke="#303b50" stroke-width="1">'
        )
        for level in (0.25, 0.5, 0.75, 1):
            parts.append(
                f'<polygon points="{polygon(radius * level)}"/>'
            )

        for i in range(count):
            x, y = point(i, radius)
            parts.append(
                f'<line x1="{cx}" y1="{cy}" x2="{x:.2f}" y2="{y:.2f}"/>'
            )
        parts.append("</g>")

        values = [byte_count / total_bytes for _, byte_count in languages]
        coords = [
            point(i, radius * values[i])
            for i in range(count)
        ]
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in coords)

        parts.append(
            f'<polygon points="{points}" fill="#36bcf7" '
            'fill-opacity=".22" stroke="#36bcf7" stroke-width="3" '
            'stroke-linejoin="round"/>'
        )

        for x, y in coords:
            parts.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" '
                'fill="#a5f3fc" stroke="#0d1117" stroke-width="2"/>'
            )

        for i, (language, byte_count) in enumerate(languages):
            x, y = point(i, 166)
            share = byte_count / total_bytes * 100
            parts.append(
                f'<text x="{x:.2f}" y="{y:.2f}" fill="#e6edf3" '
                'font-family="Arial,sans-serif" font-size="12" '
                'text-anchor="middle" dominant-baseline="middle">'
                f'{html.escape(language)} · {share:.1f}%</text>'
            )

        parts.append(
            '<rect x="70" y="400" width="620" height="75" rx="12" '
            'fill="#161b22" stroke="#303b50"/>'
        )
        parts.append(
            '<text x="90" y="425" fill="#36bcf7" '
            'font-family="Arial,sans-serif" font-size="13" '
            'font-weight="700">WHAT THESE PERCENTAGES MEAN</text>'
        )
        parts.append(
            '<text x="90" y="448" fill="#c9d1d9" '
            'font-family="Arial,sans-serif" font-size="12">'
            'Share of detected code bytes, not skill or proficiency.</text>'
        )

    parts.extend([
        f'<text x="380" y="510" fill="#8b949e" text-anchor="middle" '
        f'font-family="Arial,sans-serif" font-size="11">'
        f'Generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}'
        '</text>',
        '</svg>',
    ])

    with open(OUTPUT, "w", encoding="utf-8") as file:
        file.write("\n".join(parts) + "\n")


if __name__ == "__main__":
    try:
        language_totals = get_all_languages()
        make_svg(language_totals)
        print(f"Updated {OUTPUT}")
        print(f"Languages found: {len(language_totals)}")
    except (urllib.error.HTTPError, urllib.error.URLError) as error:
        raise SystemExit(f"GitHub API request failed: {error}")
