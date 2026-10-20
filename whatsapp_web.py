"""Sebastian 2.3 — zakładka „WhatsApp”: stan połączenia, podgląd i wysyłka przeglądu, historia rozmowy."""
import contextlib
from pathlib import Path
from flask import abort, flash, redirect, render_template, request, send_file, session

import whatsapp as W


def register(app, s):
    @app.route('/whatsapp')
    def whatsapp_page():
        W.bind(s)
        with contextlib.closing(W.db()) as con:
            briefs = [dict(b) for b in con.execute('SELECT * FROM briefs ORDER BY id DESC LIMIT 5')]
            talk = [dict(r) for r in con.execute(
                "SELECT * FROM (SELECT 'ty' who, kind, text body, received t, note FROM inbox "
                "UNION ALL SELECT 'sebastian', kind, body, created, COALESCE(error, status) FROM outbox WHERE kind<>'make') "
                "ORDER BY t DESC LIMIT 40")]
            info = {k: W.meta_get(con, k, '') for k in ('heartbeat', 'connected', 'linked_as', 'sent:rano', 'mute_until', 'logged_out')}
            pending = con.execute("SELECT COUNT(*) FROM outbox WHERE status='pending'").fetchone()[0]
            errors = con.execute("SELECT COUNT(*) FROM outbox WHERE status='error'").fetchone()[0]
        return render_template('whatsapp.html', c=W.C, checks=W.checks(), briefs=briefs, talk=talk, info=info,
                               pending=pending, errors=errors, running=W.agent_loaded(), name=W.owner_name(),
                               engine=W.voice_engine(), csrf=session['csrf'])

    @app.route('/whatsapp/akcja', methods=['POST'])
    def whatsapp_action():
        W.bind(s)
        action = request.form.get('akcja', '')
        kind = request.form.get('rodzaj', 'rano')
        if kind not in W.WHAT:
            abort(400)
        with contextlib.closing(W.db()) as con:
            if action == 'preview':
                W.make_brief(con, kind, send=False)
                flash('Podgląd gotowy (niczego nie wysłano) — poniżej tekst i nagranie.')
            elif action == 'send':
                if not W.C.WA_ENABLED:
                    flash('Najpierw skonfiguruj WhatsApp: python sebastian.py wa-setup')
                else:
                    W.enqueue(con, 'make', kind, purpose='manual')
                    flash('Zlecono: usługa w tle złoży przegląd i wyśle go na WhatsApp (zwykle 1–3 minuty).'
                          + ('' if W.agent_loaded() or W.C.WA_TRANSPORT == 'plik' else ' Uwaga: usługa nie działa — python sebastian.py wa-start'))
            elif action == 'test':
                W.enqueue(con, 'text', f"Cześć{', ' + W.owner_name() if W.owner_name() else ''}! Tu Sebastian — wiadomość testowa z panelu. "
                                       "Napisz „pomoc”, żeby zobaczyć, co potrafię.", purpose='manual')
                flash('Wiadomość testowa w kolejce.')
            elif action == 'retry':
                n = con.execute("UPDATE outbox SET status='pending', attempts=0, error=NULL WHERE status='error'").rowcount
                con.commit()
                flash(f'Ponowię wysyłkę: {n}.')
            elif action == 'unmute':
                W.meta_set(con, 'mute_until', '')
                flash('Powiadomienia włączone.')
            else:
                abort(400)
        return redirect('/whatsapp')

    @app.route('/whatsapp/nagranie/<int:bid>')
    def whatsapp_audio(bid):
        W.bind(s)
        with contextlib.closing(W.db()) as con:
            b = con.execute('SELECT audio FROM briefs WHERE id=?', (bid,)).fetchone()
        if not b or not b['audio']:
            abort(404)
        path = Path(b['audio'])
        if not path.exists() or W.home() not in path.resolve().parents:
            abort(404)
        return send_file(path, mimetype='audio/wav')
