import os, io, json, math, sqlite3, datetime
import pandas as pd
import streamlit as st
from PIL import Image

st.set_page_config(page_title="RemontAI", page_icon="🏠", layout="wide")
CAT = pd.read_csv("catalog.csv").fillna("")
MODELS = [os.getenv("GEMINI_MODEL", "gemini-3.8-flash"), "gemini-3.7-flash"]
WORKS = {"walls_paint": "Покраска стен", "walls_wallpaper": "Поклейка обоев",
         "floor_laminate": "Укладка ламината", "ceiling_paint": "Покраска потолка",
         "plinth": "Монтаж плинтуса"}
TIERS = ["эконом", "оптимум", "премиум"]

def get_key():
    try:
        return os.getenv("GEMINI_API_KEY") or st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None

@st.cache_resource
def get_client():
    from google import genai
    from google.genai import types
    return genai.Client(api_key=get_key(), http_options=types.HttpOptions(timeout=30000))  # 30 секунд

def gemini(contents):
    import time
    err = None
    for attempt in range(2):
        busy = False
        for m in MODELS:
            try:
                return get_client().models.generate_content(model=m, contents=contents).text
            except Exception as e:
                err = e
                t = str(e)
                if "429" in t or "RESOURCE_EXHAUSTED" in t:
                    continue  # дневной лимит этой модели исчерпан: сразу пробуем другую
                busy = busy or "503" in t or "UNAVAILABLE" in t
        if not busy:
            break
        time.sleep(4)  # перегрузка Google: одна короткая повторная попытка
    raise err

@st.cache_data(show_spinner=False)
def analyze_cached(b, room, style):
    return analyze(Image.open(io.BytesIO(b)).convert("RGB"), room, style)

def analyze(img, room, style):
    p = (f"Ты опытный прораб в Алматы. По фото комнаты ({room}, желаемый стиль: {style}) оцени состояние поверхностей. "
         'Верни ТОЛЬКО JSON: {"walls":"кратко","floor":"кратко","ceiling":"кратко","works":[...],"reason":"1-2 предложения"}. '
         f"Поле works только из списка {list(WORKS)}; выбирай лишь то, что реально нужно по фото.")
    img = img.copy(); img.thumbnail((1024, 1024))  # уменьшаем фото: быстрее и дешевле
    t = gemini([p, img]).strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(t)

def calc(L, W, H, works, tier):
    walls, floor, per = 2 * (L + W) * H * 0.9, L * W, 2 * (L + W) - 0.9
    area = {"walls_paint": walls, "walls_wallpaper": walls, "floor_laminate": floor, "ceiling_paint": floor, "plinth": per}
    rows = []
    for w in works:
        for _, r in CAT[(CAT.work == w) & (CAT.tier.isin([tier, "любой"]))].iterrows():
            q = math.ceil(area[w] * r.layers * 1.1 / r.coverage)  # запас 10%
            rows.append({"Работа": WORKS[w], "Материал": r.material, "Кол-во": q, "Ед.": r.unit,
                         "Цена, ₸": int(r.price), "Сумма, ₸": int(q * r.price), "Магазин": r.store,
                         "Ссылка": r.url, "Цена проверена": r.verified})
    return pd.DataFrame(rows, columns=["Работа", "Материал", "Кол-во", "Ед.", "Цена, ₸", "Сумма, ₸", "Магазин", "Ссылка", "Цена проверена"])

def make_xlsx(df):
    b = io.BytesIO()
    out = pd.concat([df, pd.DataFrame([{"Материал": "ИТОГО", "Сумма, ₸": int(df["Сумма, ₸"].sum())}])])
    out.to_excel(b, index=False, sheet_name="Смета")
    return b.getvalue()

def make_pdf(df, title):
    from fpdf import FPDF
    font = next((p for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"] if os.path.exists(p)), None)
    if not font:
        return None
    pdf = FPDF(orientation="L"); pdf.add_page(); pdf.add_font("D", fname=font)
    pdf.set_font("D", size=13); pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT"); pdf.set_font("D", size=9)
    cols, ws = ["Работа", "Материал", "Кол-во", "Ед.", "Цена, ₸", "Сумма, ₸"], [45, 95, 20, 35, 28, 32]
    for c, w in zip(cols, ws): pdf.cell(w, 7, c, border=1)
    pdf.ln()
    for _, r in df.iterrows():
        for c, w in zip(cols, ws): pdf.cell(w, 7, str(r[c])[:55], border=1)
        pdf.ln()
    pdf.set_font("D", size=11); pdf.cell(0, 10, f"ИТОГО: {int(df['Сумма, ₸'].sum()):,} ₸".replace(",", " "), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("D", size=8); pdf.cell(0, 6, "Смета ориентировочная и не заменяет замер и осмотр мастера.")
    return bytes(pdf.output())

def db():
    con = sqlite3.connect("projects.db")
    con.execute("create table if not exists p(id integer primary key, ts text, name text, total int, data text)")
    return con

fmt = lambda v: f"{int(v):,} ₸".replace(",", " ")
st.title("🏠 RemontAI")
st.caption("От фото комнаты до сметы ремонта · Алматы")
st.warning("Цены в демо-каталоге ориентировочные. Смета не заменяет замер и осмотр мастера.")
tab1, tab2 = st.tabs(["Новая смета", "Мои проекты"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        up = st.file_uploader("Фото комнаты", type=["jpg", "jpeg", "png"])
        room = st.selectbox("Тип комнаты", ["Гостиная", "Спальня", "Кухня", "Детская", "Коридор"])
        style = st.selectbox("Стиль", ["Современный", "Скандинавский", "Лофт", "Классика", "Минимализм"])
        lang = st.radio("Язык пояснений", ["Русский", "Қазақша"], horizontal=True)
    with c2:
        L = st.number_input("Длина, м", 1.0, 15.0, 4.5, 0.1)
        W = st.number_input("Ширина, м", 1.0, 15.0, 3.5, 0.1)
        H = st.number_input("Высота потолка, м", 2.0, 4.5, 2.7, 0.1)
        budget = st.number_input("Бюджет на материалы, ₸", 0, 20_000_000, 600_000, 10_000)
        if up:
            img = Image.open(up).convert("RGB"); st.image(img, width="stretch")
    if up and st.button("🔍 Проанализировать фото"):
        if not get_key():
            st.error("Не задан GEMINI_API_KEY. Можно выбрать работы вручную ниже.")
        else:
            with st.spinner("ИИ анализирует фото..."):
                try: st.session_state.ai = analyze_cached(up.getvalue(), room, style)
                except Exception as e: st.error(f"Ошибка ИИ: {e}")
    ai = st.session_state.get("ai")
    if ai:
        st.subheader("Что ИИ увидел на фото")
        st.write(f"**Стены:** {ai.get('walls')}  \n**Пол:** {ai.get('floor')}  \n**Потолок:** {ai.get('ceiling')}  \n**Почему такие работы:** {ai.get('reason')}")
    default = [w for w in (ai or {}).get("works", []) if w in WORKS] or ["walls_paint", "floor_laminate"]
    works = st.multiselect("Работы (можно убрать лишнее)", list(WORKS), default=default, format_func=WORKS.get)
    if works:
        tot = {t: int(calc(L, W, H, works, t)["Сумма, ₸"].sum()) for t in TIERS}
        for col, (t, v) in zip(st.columns(3), tot.items()):
            col.metric(t.capitalize(), fmt(v), "в бюджете" if v <= budget else "выше бюджета", delta_color="normal" if v <= budget else "inverse")
        fit = [i for i, t in enumerate(TIERS) if tot[t] <= budget]
        tier = st.radio("Выбранный вариант", TIERS, index=fit[-1] if fit else 0, horizontal=True)
        df = calc(L, W, H, works, tier)
        st.dataframe(df, width="stretch", hide_index=True)
        st.subheader(f"Итого: {fmt(df['Сумма, ₸'].sum())}")
        if st.button("💬 Объяснить выбор"):
            if not get_key(): st.error("Нужен GEMINI_API_KEY.")
            else:
                q = (f"Ответь на языке: {lang}. Клиент планирует ремонт ({room}, стиль {style}), бюджет {budget} ₸. "
                     f"Суммы по вариантам: {tot}. Выбран вариант «{tier}», работы: {[WORKS[w] for w in works]}. "
                     "Объясни простыми словами за 3-4 предложения, почему этот выбор разумен и на чём можно сэкономить. Не выдумывай цен.")
                try: st.info(gemini(q))
                except Exception as e: st.error(f"Ошибка ИИ: {e}")
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇️ Excel", make_xlsx(df), "smeta.xlsx")
        pdf = make_pdf(df, f"Смета ремонта: {room}, {L}x{W} м, вариант «{tier}»")
        if pdf: d2.download_button("⬇️ PDF", pdf, "smeta.pdf")
        name = d3.text_input("Название проекта", f"{room} {L}x{W}")
        if d3.button("💾 Сохранить проект"):
            con = db(); con.execute("insert into p(ts,name,total,data) values(?,?,?,?)",
                (datetime.datetime.now().strftime("%d.%m.%Y %H:%M"), name, int(df["Сумма, ₸"].sum()), df.to_json(force_ascii=False)))
            con.commit(); st.success("Проект сохранён во вкладке «Мои проекты»")

with tab2:
    rows = db().execute("select id,ts,name,total,data from p order by id desc").fetchall()
    if not rows: st.info("Сохранённых проектов пока нет.")
    for i, ts, name, total, data in rows:
        with st.expander(f"{name} · {ts} · {fmt(total)}"):
            st.dataframe(pd.read_json(io.StringIO(data)), width="stretch", hide_index=True)
