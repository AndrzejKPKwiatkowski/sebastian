"""Sebastian 2.0 — zakładka „Nauka” w panelu (tylko podgląd, nic nie zmienia)."""
import contextlib, re
from pathlib import Path
from flask import render_template, request, session

import learner as L


def register(app, s):
    @app.route('/learner')
    def learner_page():
        L.bind(s)
        with contextlib.closing(L.db()) as con:
            st = L.stats(con)
            folders = [dict(r) for r in con.execute('SELECT * FROM history_folders ORDER BY account, folder')]
            meta = {k: L.meta_get(con, k, '') for k in ('last_consolidation', 'last_current', 'last_rag_sync', 'last_mail_scan', 'last_scan')}
            q = request.args.get('q', '').strip()[:200]
            recent = [dict(r) for r in con.execute(
                "SELECT id, name, path, modified, status, note FROM files WHERE (id LIKE 'mail:%' OR id LIKE 'import:%') "
                "AND (? = '' OR name LIKE ? OR path LIKE ?) ORDER BY modified DESC LIMIT 40", (q, f'%{q}%', f'%{q}%'))]
        out = L.LEARN / 'wyniki'
        read = lambda name: (out / name).read_text(encoding='utf-8') if (out / name).exists() else ''
        log_path = Path(s.DATA) / 'logs' / 'learner.log'
        tail = log_path.read_text(encoding='utf-8', errors='replace').splitlines()[-25:] if log_path.exists() else []
        running = (Path.home() / 'Library/LaunchAgents/pl.sebastian.learner.plist').exists()
        return render_template('learner.html', st=st, folders=folders, meta=meta, recent=recent, q=q,
                               current=read('Biezace_sprawy.md'), profile=read('Profil_wiedzy.md'),
                               tail=tail, running=running, model=L.C.MODEL, csrf=session['csrf'],
                               scope=request.args.get('scope', 'private'))
