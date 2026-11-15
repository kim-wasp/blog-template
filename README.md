# 내 블로그

콘텐츠 스튜디오가 posts/ 에 글을 넣으면 Cloudflare가 build.py 로 사이트를 만들어 띄워요.

- 이름, 소개, 분류, 광고: site.yml
- 소개, 편집 원칙 페이지: pages/about.html, pages/editorial.html
- 로고와 아이콘: static/ (favicon.svg, logo.png, og.png, apple-touch-icon.png)
- Cloudflare 빌드 명령: `pip install -r requirements.txt && python3 build.py`, 배포 명령: `npx wrangler deploy`
- 새 글 검색엔진 알림(IndexNow): 영문·숫자 키를 하나 정해 static/<키>.txt 파일(내용은 키 그대로)로 넣고, 스튜디오 사이트 설정 indexnow_key 에 같은 키를 적어요
