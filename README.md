# Medicine Recommendation System

## Folder layout
```
med_rec/
  main.py
  report_pdf.py                 <- builds the downloadable PDF report
  templates/  base.html, index.html, login.html, about.html, contact.html, developer.html, blog.html, how_to_use.html
  static/css/style.css
  static/js/app.js
  models/svc_model.pkl          <- copy your existing model here
  data/*.csv                    <- copy your existing CSV files here
```

## Run
```
python -m pip install flask pandas numpy scikit-learn reportlab
python main.py            # http://127.0.0.1:5000  (login: admin / admin)
```
Optional environment variables: `MEDREC_SECRET_KEY`, `MEDREC_USERNAME`, `MEDREC_PASSWORD`, `FLASK_DEBUG=1`.

The patient photo is kept in memory for the report only; it is never saved to disk.
The CALL Emergency button shows the calling screen only - it does not place a real phone call.

Dark mode: use the moon/sun button in the top bar. The choice is remembered in the browser.

Developer: Sahana S - https://www.linkedin.com/in/sahana-s-3078552bb
