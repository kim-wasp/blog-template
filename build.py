"""정적 블로그 만들기 → dist/ (site.yml 과 pages/ 를 바꿔서 내 블로그로)

글: posts/<날짜>-<슬러그>/post.md (맨 위 --- 사이에 정보, 아래는 마크다운 본문), 사진은 같은 폴더
  정보: title, description, date, category, conclusion(한 줄 결론), hero(사진 파일), sources, draft
  본문 규칙:
    ## 소제목 → 번호가 붙는 핵심 포인트
    ## 편집자 생각 → 글 아래 청록 띠로 따로 보여요 (사장님 의견)
    ## 더 자세히 → 그 아래 전부가 접힌 '더 자세히 보기' 안에 들어가요 (표, 일정, 쟁점)
실행: python3 build.py   (Cloudflare 빌드 명령)
"""
import datetime as dt
import html
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote

import markdown
import yaml

ROOT = Path(__file__).parent
OUT = ROOT / "dist"
SITE = yaml.safe_load((ROOT / "site.yml").read_text(encoding="utf-8"))
URL = SITE["url"].rstrip("/")
ADS = os.environ.get("ADSENSE_CLIENT") or (SITE.get("ads") or {}).get("adsense_client") or ""
CATS = {c["name"]: c["slug"] for c in SITE["categories"]}
KST = dt.timezone(dt.timedelta(hours=9))
_V = SITE.get("verification") or {}
VERIFY = "".join(f'<meta name="{n}" content="{html.escape(str(_V[k]))}">' for k, n in
                 (("google", "google-site-verification"), ("naver", "naver-site-verification"), ("bing", "msvalidate.01")) if _V.get(k))
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@600&display=swap">'
         '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">')


def esc(s):
    return html.escape(str(s or ""), quote=True)


def md_html(text):
    md = markdown.Markdown(extensions=["tables", "sane_lists"])
    h = md.convert(text or "")
    h = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener nofollow"', h)
    h = re.sub(r"<img ", '<img loading="lazy" ', h)
    return h.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")


def split_sections(body):
    """본문을 핵심 / 편집자 생각 / 더 자세히 로 나눠요"""
    main, opinion, more = [], [], []
    cur = main
    for part in re.split(r"(?m)^(?=## )", body):
        head = part.split("\n", 1)[0].strip()
        if head == "## 편집자 생각":
            cur = opinion
            part = part.split("\n", 1)[1] if "\n" in part else ""
        elif head == "## 더 자세히":
            cur = more
            part = part.split("\n", 1)[1] if "\n" in part else ""
        elif cur is opinion and head.startswith("## "):
            cur = more if more else main
        cur.append(part)
    return "".join(main), "".join(opinion).strip(), "".join(more).strip()


# ---------- 글 읽기 ----------
def load_posts():
    posts = []
    today = dt.datetime.now(KST).date().isoformat()
    for f in sorted((ROOT / "posts").glob("*/post.md")):
        raw = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
        if not m:
            print(f"건너뜀 (정보 없음): {f}")
            continue
        meta, body = yaml.safe_load(m.group(1)) or {}, m.group(2)
        if meta.get("draft") and not os.environ.get("PREVIEW_DRAFTS"):
            continue
        d = f.parent
        slug = meta.get("slug") or re.sub(r"^\d{4}-\d{2}-\d{2}-", "", d.name)
        date = meta.get("date") or d.name[:10]
        date = date.isoformat() if isinstance(date, (dt.date, dt.datetime)) else str(date)
        if date[:10] > today:
            continue  # 예약 글은 그날부터
        main, opinion, more = split_sections(body)
        chars = len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", md_html(main))))
        posts.append({**meta, "slug": slug, "date": date, "updated": str(meta.get("updated") or ""), "dir": d,
                      "main": md_html(main), "opinion": md_html(opinion) if opinion else "", "more": md_html(more) if more else "",
                      "minutes": max(1, round(chars / 600)),
                      "category": meta.get("category") if meta.get("category") in CATS else list(CATS)[0]})
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return posts


def kdate(d):
    return f"{d[:4]}년 {int(d[5:7])}월 {int(d[8:10])}일" if d else ""


def post_url(p):
    return f"/posts/{p['slug']}/"


def hero_url(p):
    return f"/posts/{p['slug']}/{p['hero']}" if p.get("hero") else ""


def line(p):
    return p.get("conclusion") or p.get("description", "")


# ---------- 틀 ----------
def layout(title, body, *, desc="", path="/", og_img="", og_type="website", extra_head="", active=""):
    canon = URL + path
    full_title = title if title == SITE["name"] else f"{title} | {SITE['name']}"
    links = "".join(f'<a href="/category/{s}/"{" aria-current=\"page\"" if active == n else ""}>{esc(n)}</a>' for n, s in CATS.items())
    ads_head = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADS}" crossorigin="anonymous"></script>'
                if ADS else "")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="max-image-preview:large">
<title>{esc(full_title)}</title><meta name="description" content="{esc(desc or SITE['description'])}">
<link rel="canonical" href="{canon}"><link rel="alternate" type="application/rss+xml" title="{esc(SITE['name'])}" href="{URL}/rss.xml">
<meta property="og:site_name" content="{esc(SITE['name'])}"><meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc or SITE['description'])}"><meta property="og:url" content="{canon}"><meta property="og:type" content="{og_type}">
<meta property="og:image" content="{URL + (og_img or '/og.png')}"><meta name="twitter:card" content="summary_large_image">
{VERIFY}<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="/apple-touch-icon.png">{FONTS}
<link rel="stylesheet" href="/css/site.css">{ads_head}{extra_head}</head><body>
<a class="skip" href="#main">본문으로 건너뛰기</a>
<header class="nav"><div class="container nav__in"><a class="wordmark" href="/" aria-label="{esc(SITE['name'])}"><span class="bj bj--o" aria-hidden="true">시</span><span class="bj bj--o" aria-hidden="true">시</span><span class="bj bj--x" aria-hidden="true">비</span><span class="bj bj--x" aria-hidden="true">비</span><span aria-hidden="true">노트</span></a><nav class="nav__links" aria-label="분류">{links}</nav></div></header>
<main id="main">{body}</main>
<footer class="foot"><div class="container"><p class="foot__mast">{esc(SITE['tagline'])}</p>
<div class="foot__row"><nav class="foot__links" aria-label="사이트 안내"><a href="/about/">소개</a><a href="/editorial/">편집 원칙</a><a href="/privacy/">개인정보처리방침</a><a href="/contact/">문의</a><a href="/rss.xml">RSS</a></nav>
<p>© {dt.date.today().year} {esc(SITE['name'])}</p></div></div></footer></body></html>"""


def ad_slot():
    return (f'<div class="ad"><ins class="adsbygoogle" style="display:block" data-ad-client="{ADS}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>') if ADS else ""


def row(p):
    return (f'<li><a class="row" href="{post_url(p)}"><span class="row__meta"><span class="label">{esc(p["category"])}</span>'
            f'<span class="label">{kdate(p["date"])}</span></span><span class="row__body"><span class="row__title">{esc(p["title"])}</span>'
            f'<span class="row__line">{esc(line(p))}</span></span><span class="label">{p["minutes"]}분 읽기</span></a></li>')


def write(path, text):
    f = OUT / path.lstrip("/")
    if path.endswith("/"):
        f = f / "index.html"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


# ---------- 페이지 ----------
WAYS = [("결론부터", "첫 줄에 한 줄 결론. 바쁘면 거기까지만 읽어도 돼요."),
        ("쉬운 말로", "법안 이름, 숫자, 절차를 처음 보는 사람도 알게 풀어요."),
        ("양쪽 다", "갈리는 쟁점은 각 입장의 가장 센 근거를 나란히 놓아요."),
        ("출처는 끝까지", "숫자와 발언은 원문을 확인하고, 글 끝에 링크를 남겨요.")]


def home(posts):
    per = SITE.get("per_page", 12)
    lead = posts[0] if posts else None
    if lead:
        fig = f'<figure class="hero__fig"><img src="{hero_url(lead)}" alt="{esc(lead.get("hero_alt") or "")}"></figure>' if lead.get("hero") else ""
        hero = (f'<section class="hero" aria-labelledby="lead-title"><div class="hero__text">'
                f'<h1 id="lead-title">{esc(lead["title"])}</h1><p class="conclusion-line">{esc(line(lead))}</p>'
                f'<div class="actions"><a class="btn" href="{post_url(lead)}">{lead["minutes"]}분 만에 읽기</a><a class="link" href="#recent">지난 글</a></div></div>{fig}</section>')
    else:
        hero = (f'<section class="hero" aria-labelledby="lead-title"><div class="hero__text"><h1 id="lead-title">{esc(SITE.get("tagline", ""))}</h1>'
                f'<p class="conclusion-line">{esc(SITE.get("description", ""))}</p>'
                f'<div class="actions"><a class="btn" href="/about/">어떻게 쓰는지 보기</a></div></div></section>')
    rest = posts[1:per + 1]
    recent = (f'<section class="section" id="recent" aria-labelledby="recent-h"><div class="section__head"><h2 id="recent-h">지난 글</h2></div>'
              + (f'<ul class="index">{"".join(row(p) for p in rest)}</ul>' if rest else '<p class="empty">첫 글을 준비하고 있어요.</p>')
              + (f'<div class="pager"><span></span><a class="link" href="/page/2/">더 지난 글</a></div>' if len(posts) > per + 1 else "") + "</section>")
    ways = ('<section class="ways" aria-labelledby="ways-h"><div class="container ways__grid"><h2 id="ways-h">이렇게 써요</h2><ul class="spec">'
            + "".join(f"<li><b>{esc(a)}</b><p>{esc(b)}</p></li>" for a, b in WAYS) + "</ul></div></section>")
    write("/", layout(SITE["name"], f'<div class="container">{hero}{recent}</div>{ways}', path="/"))
    # 2쪽부터
    older = posts[per + 1:]
    pages = -(-len(older) // per)
    for n in range(pages):
        chunk = older[n * per:(n + 1) * per]
        path = f"/page/{n + 2}/"
        prev = "/" if n == 0 else f"/page/{n + 1}/"
        nxt = f'<a class="link" href="/page/{n + 3}/">더 지난 글</a>' if n + 1 < pages else "<span></span>"
        body = (f'<section class="section"><div class="section__head"><h1>지난 글 {n + 2}쪽</h1></div><ul class="index">{"".join(row(p) for p in chunk)}</ul>'
                f'<div class="pager"><a class="link" href="{prev}">최근 글</a>{nxt}</div></section>')
        write(path, layout(f"지난 글 {n + 2}쪽", f'<div class="container">{body}</div>', path=path))


def category_pages(posts):
    for name, slug in CATS.items():
        items = [p for p in posts if p["category"] == name]
        body = (f'<section class="section"><div class="section__head"><h1>{esc(name)}</h1></div>'
                + (f'<ul class="index">{"".join(row(p) for p in items)}</ul>' if items else '<p class="empty">이 분류에는 아직 글이 없어요.</p>') + "</section>")
        write(f"/category/{slug}/", layout(name, f'<div class="container">{body}</div>', path=f"/category/{slug}/", desc=f"{name} 이슈를 결론부터 쉽게 정리한 글", active=name))


def issue_keys(p):
    """태그 앞 두 단어 = 이슈 이름 (예: '조작기소 특검법 통과' → '조작기소 특검법')"""
    return {" ".join(str(t).split()[:2]) for t in (p.get("tags") or []) if len(str(t).split()) >= 2}


def issue_flow(p, posts):
    """같은 이슈를 다룬 글을 날짜순으로 이어 줘요 (후속 글끼리 서로 링크 → 독자와 검색엔진이 흐름을 알게)"""
    k = issue_keys(p)
    flow = sorted([q for q in posts if issue_keys(q) & k], key=lambda q: (q["date"], q["slug"]))
    if len(flow) < 2:
        return "", []
    items = "".join(
        (f'<li aria-current="page"><span class="meta">{kdate(q["date"])}</span> <b>{esc(q["title"])}</b> <span class="meta">지금 보는 글</span></li>' if q is p else
         f'<li><span class="meta">{kdate(q["date"])}</span> <a href="{post_url(q)}">{esc(q["title"])}</a></li>') for q in flow)
    return (f'<section class="flow" aria-labelledby="flow-h"><h2 id="flow-h" class="label">이 이슈 흐름</h2><ol>{items}</ol></section>', flow)


def post_page(p, posts):
    path = post_url(p)
    upd = f'<span>고침 {kdate(p["updated"])}</span>' if p.get("updated") and p["updated"][:10] != p["date"][:10] else ""
    head = (f'<header class="post__head"><a class="label" href="/category/{CATS[p["category"]]}/">{esc(p["category"])}</a>'
            f'<h1>{esc(p["title"])}</h1><p class="meta"><span>{kdate(p["date"])}</span><span>{p["minutes"]}분 읽기</span>{upd}</p>'
            + (f'<div class="well"><span class="label">한 줄 결론</span><p>{esc(p["conclusion"])}</p></div>' if p.get("conclusion") else "")
            + (f'<figure class="post__fig"><img src="{esc(p["hero"])}" alt="{esc(p.get("hero_alt") or "")}"></figure>' if p.get("hero") else "")
            + "</header>")
    main = p["main"]
    if ADS:
        parts = main.split("<h2", 2)
        if len(parts) == 3:
            main = parts[0] + "<h2" + parts[1] + ad_slot() + "<h2" + parts[2]
    more = (f'<details class="more"><summary>더 자세히 보기</summary><div class="prose">{p["more"]}</div></details>' if p["more"] else "")
    sources = ""
    if p.get("sources"):
        sources = ('<section class="sources" aria-labelledby="src-h"><h2 id="src-h" class="label">출처</h2><ol>' + "".join(
            f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener nofollow">{esc(s.get("title") or s["url"])}</a></li>' for s in p["sources"]) + "</ol></section>")
    share = (f'<div class="actions share"><button class="link" type="button" onclick="navigator.clipboard.writeText(location.href).then(()=>{{this.textContent=\'링크를 복사했어요\'}})">링크 복사</button>'
             f'<a class="link" href="https://twitter.com/intent/tweet?url={quote(URL + path)}&text={quote(p["title"])}" target="_blank" rel="noopener">X에 공유</a>'
             f'<a class="link" href="https://www.facebook.com/sharer/sharer.php?u={quote(URL + path)}" target="_blank" rel="noopener">페이스북에 공유</a></div>')
    top = f'<article class="post">{head}<div class="post__body"><div class="prose">{main}</div></div></article>'
    flow_html, flow = issue_flow(p, posts)
    tail = (f'<div class="post post--tail"><div class="post__body">{flow_html}{more}{sources}'
            f'<p class="fix">사실과 다른 부분이 있으면 <a href="/contact/">알려주세요</a>. 확인 후 고치고 고친 날짜를 남겨요.</p>{share}</div></div>')
    opinion = (f'<section class="opinion" aria-labelledby="op-h"><div class="container opinion__in"><div><h2 id="op-h">편집자 생각</h2>'
               f'<p class="note">위 정리와 별개인, {esc(SITE["name"])} 편집자의 개인 의견이에요.</p><div class="prose">{p["opinion"]}</div></div></div></section>'
               if p["opinion"] else "")
    same = [q for q in posts if q["slug"] != p["slug"] and q not in flow and q["category"] == p["category"]][:3]
    same += [q for q in posts if q["slug"] != p["slug"] and q not in flow and q not in same][:3 - len(same)]
    related = (f'<section class="section" aria-labelledby="rel-h"><div class="section__head"><h2 id="rel-h">함께 읽을 글</h2></div><ul class="index">{"".join(row(q) for q in same)}</ul></section>'
               if same else "")
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": p["title"], "description": p.get("description", ""),
          "datePublished": p["date"], "dateModified": p.get("updated") or p["date"], "mainEntityOfPage": URL + path,
          "author": {"@type": "Organization", "name": SITE["author"], "url": URL + "/about/"},
          "publisher": {"@type": "Organization", "name": SITE["name"], "logo": {"@type": "ImageObject", "url": URL + "/logo.png"}}}
    if p.get("hero"):
        ld["image"] = [URL + hero_url(p)]
    html_ = layout(p["title"], f'<div class="container">{top}</div>{opinion}<div class="container">{tail}{ad_slot()}{related}</div>', desc=p.get("description") or line(p), path=path, og_img=hero_url(p), og_type="article",
                   extra_head=f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>', active=p["category"])
    write(path, html_)
    for f in p["dir"].iterdir():
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"):
            (OUT / path.strip("/")).mkdir(parents=True, exist_ok=True)
            shutil.copy(f, OUT / path.strip("/") / f.name)


def page_file(name):
    """pages/<name>.html 을 읽어요. {name}, {tagline}, {email} 은 site.yml 값으로 바뀌어요."""
    f = ROOT / "pages" / f"{name}.html"
    t = f.read_text(encoding="utf-8") if f.exists() else f"<h1>{name}</h1>"
    return (t.replace("{name}", esc(SITE["name"])).replace("{tagline}", esc(SITE.get("tagline", "")))
             .replace("{email}", esc(SITE.get("contact_email") or "")))


def static_pages():
    email = SITE.get("contact_email") or ""
    pages = {
        "/about/": ("소개", page_file("about")),
        "/editorial/": ("편집 원칙", page_file("editorial")),
        "/privacy/": ("개인정보처리방침", """<h1>개인정보처리방침</h1><div class="prose">
<p>NAME(이하 사이트)는 회원가입이나 댓글 기능이 없어 방문자의 이름, 연락처 같은 개인정보를 직접 수집하지 않아요.</p>
<h2>쿠키와 광고</h2><p>사이트는 Google 애드센스 등 제3자 광고 서비스를 사용할 수 있어요. Google을 포함한 제3자 공급업체는 쿠키를 사용해 사용자가 이 사이트나 다른 웹사이트를 방문한 기록을 바탕으로 광고를 게재해요. 사용자는 <a href="https://adssettings.google.com" target="_blank" rel="noopener">Google 광고 설정</a>에서 맞춤 광고를 끌 수 있어요. 자세한 내용은 <a href="https://policies.google.com/technologies/ads" target="_blank" rel="noopener">Google 광고 정책</a>을 참고해 주세요.</p>
<h2>방문 통계</h2><p>사이트 운영 개선을 위해 방문 수, 유입 경로 같은 익명 통계를 볼 수 있어요. 이 정보로 개인을 식별하지 않아요.</p>
<h2>문의</h2><p>개인정보 관련 문의는 <a href="mailto:EMAIL">EMAIL</a> 또는 <a href="/contact/">문의 페이지</a>로 연락해 주세요.</p><p>시행일: 2026년 11월</p></div>""".replace("EMAIL", email).replace("NAME", esc(SITE["name"]))),
        "/contact/": ("문의", f"""<h1>문의</h1><div class="prose"><p>오류 제보, 정정 요청, 제휴 문의는 아래로 보내 주세요. 정정 요청은 확인 후 빠르게 반영해요.</p>
<p>이메일: {f'<a href="mailto:{email}">{email}</a>' if email else '준비 중이에요.'}</p></div>"""),
    }
    for path, (title, body) in pages.items():
        write(path, layout(title, f'<div class="container page"><div>{body}</div></div>', path=path))
    write("/404.html", layout("페이지를 찾을 수 없어요", '<div class="container page"><div><h1>페이지를 찾을 수 없어요</h1><p class="actions" style="margin-top:24px"><a class="btn" href="/">첫 화면으로</a></p></div></div>', path="/404.html"))


def feeds(posts):
    now = dt.datetime.now(KST).date().isoformat()
    urls = [("/", now), ("/about/", ""), ("/editorial/", "")] + [(f"/category/{s}/", now) for s in CATS.values()]
    urls += [(post_url(p), (p.get("updated") or p["date"])[:10]) for p in posts]
    sm = "".join(f"<url><loc>{URL}{u}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>" for u, d in urls)
    (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding="utf-8")
    items = "".join(f"<item><title>{esc(p['title'])}</title><link>{URL}{post_url(p)}</link><guid>{URL}{post_url(p)}</guid>"
                    f"<pubDate>{dt.datetime.fromisoformat(p['date'][:10]).strftime('%a, %d %b %Y 12:00:00 +0900')}</pubDate>"
                    f"<description>{esc(line(p))}</description></item>" for p in posts[:30])
    (OUT / "rss.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(SITE["name"])}</title>'
                                 f'<link>{URL}/</link><description>{esc(SITE["description"])}</description><language>ko</language>{items}</channel></rss>', encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {URL}/sitemap.xml\n", encoding="utf-8")
    if ADS:
        (OUT / "ads.txt").write_text(f"google.com, {ADS.replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir()
    if (ROOT / "static").exists():
        shutil.copytree(ROOT / "static", OUT, dirs_exist_ok=True)
    posts = load_posts()
    home(posts)
    category_pages(posts)
    for p in posts:
        post_page(p, posts)
    static_pages()
    feeds(posts)
    (OUT / "_headers").write_text("/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  X-Frame-Options: SAMEORIGIN\n/rss.xml\n  X-Robots-Tag: noindex\n", encoding="utf-8")
    print(f"완성: 글 {len(posts)}편 → dist/")


if __name__ == "__main__":
    main()
