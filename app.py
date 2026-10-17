    # observe late React/Streamlit layout changes so the old position cannot
    # immediately come back after the rerun.
    scroll_js = r"""
    <script>
    (() => {
        const TOP_SELECTORS = [
            '[data-testid="stMainBlockContainer"]',
            '[data-testid="stMain"]',
            'section[data-testid="stMain"]',
            'section.main',
            'div.main',
            '.main'
        ];

        function getMainSurfaces() {
            const found = [];
            const seen = new Set();
            for (const selector of TOP_SELECTORS) {
                document.querySelectorAll(selector).forEach(el => {
                    if (!seen.has(el)) {
                        seen.add(el);
                        found.push(el);
                    }
                });
            }
            return found;
        }

        function resetElement(el) {
            if (!el) return;
            try {
                el.scrollTop = 0;
                el.scrollLeft = 0;
            } catch (_) {}
        }

        function resetScrollableChildren(root) {
            if (!root) return;
            const all = [root, ...root.querySelectorAll('*')];
            for (const el of all) {
                try {
                    const cs = getComputedStyle(el);
                    const scrollable =
                        el.scrollHeight > el.clientHeight + 1 &&
                        ['auto', 'scroll', 'overlay'].includes(cs.overflowY);
                    if (scrollable) resetElement(el);
                } catch (_) {}
            }
        }

        function resetRightPane() {
            try {
                const hero = document.querySelector('.fo-hero');
                const surfaces = getMainSurfaces();

                // Reset the browser/page scroll as well as Streamlit's main
                // content surfaces.
                resetElement(document.scrollingElement);
                resetElement(document.documentElement);
                resetElement(document.body);
                window.scrollTo(0, 0);

                surfaces.forEach(surface => {
                    resetElement(surface);
                    resetScrollableChildren(surface);
                });

                // Reset every scrollable ancestor of the analyzer hero.
                if (hero) {
                    let el = hero.parentElement;
                    while (el) {
                        try {
                            const cs = getComputedStyle(el);
                            if (el.scrollHeight > el.clientHeight + 1 ||
                                ['auto', 'scroll', 'overlay'].includes(cs.overflowY)) {
                                resetElement(el);
                            }
                        } catch (_) {}
                        el = el.parentElement;
                    }
                    hero.scrollIntoView({behavior: 'auto', block: 'start', inline: 'nearest'});
                }
            } catch (_) {}
        }

        // Run after the rerender and again after layout/paint settles.
        resetRightPane();
        [25, 75, 150, 300, 500, 800, 1200, 1800].forEach(ms => {
            setTimeout(resetRightPane, ms);
        });

        // Streamlit/React can append or resize blocks after the first paint.
        // Watch the main app briefly and re-apply the top position whenever
        // the analyzer DOM changes.
        const main = document.querySelector('[data-testid="stMain"]') ||
                     document.querySelector('section[data-testid="stMain"]') ||
                     document.querySelector('section.main');
        if (main && window.MutationObserver) {
            let last = Date.now();
            const observer = new MutationObserver(() => {
                const now = Date.now();
                if (now - last > 30) {
                    last = now;
                    resetRightPane();
                }
            });
            observer.observe(main, {childList: true, subtree: true, attributes: true});
            setTimeout(() => observer.disconnect(), 2500);
        }
    })();
    </script>
    """

    if hasattr(st, "html"):
        try:
            st.html(scroll_js, unsafe_allow_javascript=True)
        except TypeError:
            # Older Streamlit versions do not expose unsafe_allow_javascript.
            # Keep a harmless marker rather than breaking the application.
            st.markdown('<div id="fo-analysis-scroll-top"></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div id="fo-analysis-scroll-top"></div>', unsafe_allow_html=True)
