# Maintenance instructions for AI agents

- The homepage is `index.html` with **embedded CSS and no JavaScript**.
- Keep the page visually close to a traditional academic homepage: white background, readable text, blue links, compact information layout.
- Use the public identity **FuTseYi / Shine**, not FuXieYi. Never invent awards, papers, affiliations, or credentials.
- Preserve the Writing route `/blog/` and its existing posts.
- Blog presentation CSS is `assets/style.css`. Do not break existing `/blog/welcome/` or `/blog/posts.json`.
- For a new blog post, update static `blog/` output as well as `blog/posts.json`, unless a Markdown build pipeline is configured and verified.
- Prefer plain HTML/CSS. No Astro, React, Tailwind, animation libraries, or extra frontend scripts.
- Test links and responsive layouts before committing.
