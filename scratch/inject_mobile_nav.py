"""
inject_mobile_nav.py
Injects a mobile bottom navigation bar into every HTML page in /public.
Run once from the project root: python scratch/inject_mobile_nav.py
"""

import os, re

PUBLIC = os.path.join(os.path.dirname(__file__), '..', 'public')

# Page -> (icon, label, href)
NAV_ITEMS = [
    ('layout-dashboard', 'Home',       '/home'),
    ('users',            'Team',       '/team'),
    ('calendar',         'Events',     '/calendar'),
    ('clock',            'Attend',     '/attendance'),
    ('package',          'Inventory',  '/inventory'),
    ('zap',              'Dispatch',   '/dispatch'),
]

# Which page slug each file maps to (for active highlighting)
PAGE_ACTIVE = {
    'index.html':      '/home',
    'team.html':       '/team',
    'calendar.html':   '/calendar',
    'attendance.html': '/attendance',
    'inventory.html':  '/inventory',
    'dispatch.html':   '/dispatch',
    'admin.html':      '/admin',
    'login.html':      None,
    'print.html':      None,
}

def make_mobile_nav(active_href):
    items_html = ''
    for icon, label, href in NAV_ITEMS:
        active_class = ' active' if href == active_href else ''
        items_html += f'''
        <a href="{href}" class="mobile-nav-item{active_class}">
            <i data-lucide="{icon}" class="mnav-icon"></i>
            <span class="mnav-label">{label}</span>
        </a>'''
    return f'''
    <!-- Mobile Bottom Navigation -->
    <nav class="mobile-nav" aria-label="Mobile navigation">
        <div class="mobile-nav-inner">{items_html}
        </div>
    </nav>'''

for filename, active in PAGE_ACTIVE.items():
    path = os.path.join(PUBLIC, filename)
    if not os.path.exists(path):
        print(f'  SKIP (not found): {filename}')
        continue
    if active is None:
        print(f'  SKIP (no nav):    {filename}')
        continue

    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Remove any existing mobile-nav injection (idempotent)
    html = re.sub(
        r'\s*<!-- Mobile Bottom Navigation -->.*?</nav>',
        '',
        html,
        flags=re.DOTALL
    )

    nav_html = make_mobile_nav(active)
    # Insert just before </body>
    if '</body>' in html:
        html = html.replace('</body>', nav_html + '\n</body>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'  OK: {filename}')
    else:
        print(f'  WARN (no </body>): {filename}')

print('\nDone.')
