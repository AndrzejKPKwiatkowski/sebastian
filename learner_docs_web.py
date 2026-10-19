"""Sebastian 2.2 — zakładka „Dokumenty” w panelu: wgrywanie skanów, postęp, sprawdzanie odczytu stron."""
import contextlib, io, json, secrets
from pathlib import Path
from flask import abort, flash, redirect, render_template, request, send_file, session

import learner as L
import learner_docs as D


def register(app, s):
    def ctx():
        L.bind(s)
        return contextlib.closing(D.db())

    def job_or_404(con, jid):
        try:
            return D.get_job(con, jid)
        except RuntimeError:
            abort(404)

    @app.route('/docs')
    def docs_page():
        with ctx() as con:
            jobs = [dict(j) for j in con.execute('SELECT * FROM jobs ORDER BY id DESC LIMIT 100')]
            for j in jobs:
                j['status_pl'] = D.STATUS_PL.get(j['status'], j['status'])
                j['progress'] = D.progress_text(con, con.execute('SELECT * FROM jobs WHERE id=?', (j['id'],)).fetchone())
        ready, msg = D.vision_ready()
        return render_template('docs.html', jobs=jobs, ready=ready, msg=msg, model=L.C.DOC_VISION_MODEL,
                               inbox=str(D.inbox()), running=D.learner_running() or D.busy(),
                               ocrmypdf=bool(D.find_bin('ocrmypdf')), csrf=session['csrf'], max_mb=L.C.DOC_MAX_UPLOAD_MB)

    @app.route('/docs/upload', methods=['POST'], endpoint='docs_upload')
    def docs_upload():
        L.bind(s)
        f = request.files.get('plik')
        if not f or not f.filename:
            flash('Wybierz plik PDF albo zdjęcie skanu.')
            return redirect('/docs')
        suffix = Path(f.filename).suffix.lower()
        if suffix not in D.INPUT_EXT:
            flash('Obsługiwane są pliki PDF oraz obrazy (JPG, PNG, TIFF).')
            return redirect('/docs')
        D.root().mkdir(parents=True, exist_ok=True)
        tmp = D.root() / f'.wgrywanie-{secrets.token_hex(6)}{suffix}'
        try:
            f.save(tmp)
            if tmp.stat().st_size > L.C.DOC_MAX_UPLOAD_MB * 1024 * 1024:
                raise RuntimeError(f'Plik jest większy niż {L.C.DOC_MAX_UPLOAD_MB} MB — wrzuć go do folderu „wrzuc-tutaj”.')
            jid = D.add(tmp, request.form.get('nazwa', ''), request.form.get('typ', 'auto'), move=True,
                        src_name=Path(f.filename).name)
        except RuntimeError as e:
            flash(str(e))
            return redirect('/docs')
        finally:
            tmp.unlink(missing_ok=True)
        flash('Dodano dokument. Analiza ruszy w tle — postęp widać na tej stronie.')
        return redirect(f'/docs/{jid}')

    @app.route('/docs/<int:jid>')
    def doc_page(jid):
        filt = request.args.get('f', 'all')
        with ctx() as con:
            job = job_or_404(con, jid)
            rows = [dict(r) for r in con.execute('SELECT n, kind, conf, status, verified, text, dzial, note FROM pages '
                                                 'WHERE job_id=? ORDER BY n', (jid,))]
            for r in rows:
                r['check'] = r['status'] == 'done' and D.needs_check(r)
                r['kind_pl'] = D.KIND_PL.get(r['kind'] or '', 'czeka' if r['status'] != 'done' else '')
            counts = {'all': len(rows), 'check': sum(r['check'] for r in rows),
                      'hand': sum(1 for r in rows if r['kind'] in ('rekopis', 'mieszany'))}
            if filt == 'check':
                rows = [r for r in rows if r['check']]
            elif filt == 'hand':
                rows = [r for r in rows if r['kind'] in ('rekopis', 'mieszany')]
            progress = D.progress_text(con, job)
            edited = con.execute('SELECT COUNT(*) FROM pages WHERE job_id=? AND status=? AND entries IS NULL',
                                 (jid, 'done')).fetchone()[0]
        meta = D.job_meta(job)
        return render_template('doc.html', job=dict(job), rows=rows, counts=counts, f=filt, meta=meta, progress=progress,
                               status_pl=D.STATUS_PL.get(job['status'], job['status']), csrf=session['csrf'],
                               edited=edited and job['status'] in ('done', 'error'), folder=str(D.job_dir(job)))

    @app.route('/docs/<int:jid>/strona/<int:n>', methods=['GET', 'POST'])
    def doc_page_edit(jid, n):
        with ctx() as con:
            job = job_or_404(con, jid)
            row = con.execute('SELECT * FROM pages WHERE job_id=? AND n=?', (jid, n)).fetchone()
            if row is None:
                abort(404)
            if request.method == 'POST':
                if row['status'] != 'done':
                    flash('Ta strona nie jest jeszcze odczytana — poczekaj, aż Sebastian ją przeczyta.')
                    return redirect(f'/docs/{jid}/strona/{n}')
                text = request.form.get('text', '').replace('\r\n', '\n')
                verified = 1 if request.form.get('verified') else 0
                con.execute('UPDATE pages SET text=?, verified=?, entries=NULL WHERE job_id=? AND n=?', (text, verified, jid, n))
                con.commit()
                flash(f'Zapisano stronę {n}. Gdy skończysz poprawki, kliknij na stronie dokumentu „Złóż PDF z poprawkami”.')
                nxt = con.execute('SELECT * FROM pages WHERE job_id=? AND n>? AND status=? ORDER BY n', (jid, n, 'done')).fetchall()
                target = next((r['n'] for r in nxt if D.needs_check(r)), None) if request.form.get('go') == 'next' else None
                return redirect(f'/docs/{jid}/strona/{target or n}')
            total = job['pages']
            later = con.execute('SELECT * FROM pages WHERE job_id=? AND n>? AND status=? ORDER BY n', (jid, n, 'done')).fetchall()
            next_check = next((r['n'] for r in later if D.needs_check(r)), None)
        obs = json.loads(row['obs'] or '{}')
        alts = [a for a in json.loads(row['alts'] or '[]') if a.get('inny')]
        return render_template('doc_page.html', job=dict(job), row=dict(row), n=n, total=total, obs=D.page_obs_line(obs),
                               opis=obs.get('opis', ''), alts=alts[:60], next_check=next_check, csrf=session['csrf'],
                               kind_pl=D.KIND_PL.get(row['kind'] or '', ''), check=row['status'] == 'done' and D.needs_check(row))

    @app.route('/docs/<int:jid>/img/<int:n>')
    def doc_img(jid, n):
        import fitz
        from PIL import Image
        width = max(200, min(1600, request.args.get('w', 900, type=int)))
        with ctx() as con:
            job = job_or_404(con, jid)
        d = D.job_dir(job)
        cache = d / 'podglad' / f'{n}-{width}.jpg'
        if not cache.exists():
            src = d / 'skan.pdf' if (d / 'skan.pdf').exists() else d / 'oryginal.pdf'
            if not src.exists():
                abort(404)
            with fitz.open(src) as doc:
                if not 1 <= n <= len(doc):
                    abort(404)
                page = doc[n - 1]
                pix = page.get_pixmap(matrix=fitz.Matrix(width / page.rect.width, width / page.rect.width), alpha=False)
                img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            cache.parent.mkdir(exist_ok=True)
            img.save(cache, 'JPEG', quality=80)
        return send_file(cache, mimetype='image/jpeg', max_age=3600)

    @app.route('/docs/<int:jid>/pdf')
    def doc_pdf(jid):
        with ctx() as con:
            job = job_or_404(con, jid)
        if not job['out_name'] or not (D.job_dir(job) / job['out_name']).exists():
            abort(404)
        return send_file(D.job_dir(job) / job['out_name'], mimetype='application/pdf',
                         as_attachment=request.args.get('pobierz') == '1', download_name=job['out_name'])

    @app.route('/docs/<int:jid>/odczyt')
    def doc_text(jid):
        with ctx() as con:
            job = job_or_404(con, jid)
        path = D.job_dir(job) / 'odczyt.md'
        if not path.exists():
            abort(404)
        return send_file(path, mimetype='text/markdown', as_attachment=True, download_name=D.slug(job['name']) + '_odczyt.md')

    @app.route('/docs/<int:jid>/do-sprawdzenia.zip')
    def doc_check_zip(jid):
        with ctx() as con:
            job = job_or_404(con, jid)
        try:
            out = D.export_check(job)
        except RuntimeError as e:
            flash(str(e))
            return redirect(f'/docs/{jid}')
        return send_file(out, mimetype='application/zip', as_attachment=True, download_name=out.name)

    @app.route('/docs/<int:jid>/akcja', methods=['POST'])
    def doc_action(jid):
        action = request.form.get('akcja', '')
        with ctx() as con:
            job = job_or_404(con, jid)
            active = job['status'] in D.ACTIVE
            if action == 'pause' and active:
                D.set_job(con, jid, status='paused', paused_from=job['status'], note='wstrzymane')
                flash('Wstrzymano. Bieżąca strona zostanie dokończona.')
            elif action == 'resume' and job['status'] in ('paused', 'error'):
                back = job['paused_from'] if job['paused_from'] in D.ACTIVE else 'queued'
                D.set_job(con, jid, status=back, paused_from=None, error=None, note='wznowione')
                flash('Wznowiono.')
            elif action == 'apply' and job['status'] in ('done', 'error'):
                D.set_job(con, jid, status='structure', note='porządkowanie poprawionych stron', error=None)
                flash('Poprawione strony zostaną uporządkowane ponownie, potem powstanie nowy PDF.')
            elif action == 'rebuild' and job['status'] in ('done', 'error'):
                con.execute('UPDATE pages SET entries=NULL WHERE job_id=?', (jid,))
                D.set_job(con, jid, status='structure', note='porządkowanie od nowa', error=None)
                flash('Treść zostanie uporządkowana od nowa (strony nie są czytane ponownie).')
            elif action == 'remove':
                if request.form.get('confirm') != 'TAK':
                    flash('Aby usunąć dokument, wpisz TAK w polu potwierdzenia.')
                    return redirect(f'/docs/{jid}')
                if active and D.busy():
                    flash('Dokument jest właśnie analizowany — najpierw go wstrzymaj.')
                    return redirect(f'/docs/{jid}')
                D.cmd_remove(jid, yes=True)
                flash('Usunięto dokument.')
                return redirect('/docs')
            else:
                flash('Ta czynność nie jest teraz dostępna.')
        return redirect(f'/docs/{jid}')
