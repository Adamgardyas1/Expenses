import streamlit as st
import gspread
import pandas as pd
from datetime import datetime

# Połączenie z Google Sheets
credentials_dict = st.secrets["GS_CREDENTIALS"]
client = gspread.service_account_from_dict(credentials_dict)
sheet = client.open("Wydatki").sheet1

# Stałe
people = ["Adam", "Jacek", "Patryk"]


# Funkcje pomocnicze
def get_sheet_df():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df


def append_transaction(date, payer, participants, amount, notes=""):
    share_amount = round(amount / len(participants), 2)
    row = {"Data": date, "Osoba": payer, "Uwagi": notes}
    for person in people:
        if person == payer:
            row[person] = "0.00"
        elif person in participants:
            row[person] = f"{share_amount:.2f}"
        else:
            row[person] = "0.00"
    sheet.append_row([row["Data"], row["Osoba"], row["Adam"], row["Jacek"], row["Patryk"], row["Uwagi"]])


def calculate_balance():
    df = get_sheet_df()
    if df.empty:
        return pd.DataFrame(0, index=people, columns=people)

    # konwersja kolumn na float (mogą być stringi np. "33.33")
    for p in people:
        df[p] = pd.to_numeric(df[p], errors="coerce").fillna(0.0)

    balance = pd.DataFrame(0.0, index=people, columns=people)

    for _, row in df.iterrows():
        payer = row["Osoba"]
        for person in people:
            if person != payer:
                balance.loc[person, payer] += row[person]  # osoba winna payerowi

    # zbilansuj długi (odejmij wzajemne)
    final_balance = pd.DataFrame(0.0, index=people, columns=people)
    for p1 in people:
        for p2 in people:
            if p1 != p2:
                net = balance.loc[p1, p2] - balance.loc[p2, p1]
                final_balance.loc[p1, p2] = max(net, 0)

    return final_balance


def settle_debt(payer, receiver, amount):
    balance = calculate_balance()
    actual_debt = balance.loc[payer, receiver]

    if actual_debt <= 0:
        return False, f"{payer} nic nie jest winien {receiver}."

    # Nie pozwól na nadpłatę
    pay_amount = min(amount, actual_debt)

    row = {
        "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Osoba": payer,
        "Uwagi": f"Spłata dla {receiver}"
    }
    for person in people:
        if person == receiver:
            # payer spłaca receivera -> zmniejszamy jego dług wobec receivera
            row[person] = f"{pay_amount:.2f}"
        else:
            row[person] = "0.00"

    sheet.append_row([row["Data"], row["Osoba"], row["Adam"], row["Jacek"], row["Patryk"], row["Uwagi"]])

    if amount > actual_debt:
        return True, f"⚠️ Spłata {amount:.2f} zł była większa niż dług ({actual_debt:.2f} zł). Odjęto tylko {pay_amount:.2f} zł."
    else:
        return True, f"{payer} spłacił {receiver} {pay_amount:.2f} zł."


# Streamlit UI
st.title("Bilans Wydatków")

action = st.radio("Wybierz akcję:", ["Dodaj wydatek", "Spłać"])

if action == "Dodaj wydatek":
    payer = st.selectbox("Kto zapłacił?", people)
    participants = st.multiselect("Kto uczestniczył w wydatku?", people, default=people)
    amount = st.number_input("Kwota wydatku", min_value=0.0, step=0.01)
    notes = st.text_input("Uwagi (opcjonalnie)")
    if st.button("Dodaj wydatek"):
        append_transaction(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), payer, participants, amount, notes)
        st.success("Wydatek dodany do arkusza!")

elif action == "Spłać":
    payer = st.selectbox("Kto spłaca?", people)
    receiver = st.selectbox("Kto otrzymuje spłatę?", people)
    if payer == receiver:
        st.warning("Nie możesz spłacać sam sobie!")
    else:
        amount = st.number_input("Kwota spłaty", min_value=0.0, step=0.01)
        if st.button("Zatwierdź spłatę"):
            ok, msg = settle_debt(payer, receiver, amount)
            if ok:
                st.success(msg)
            else:
                st.warning(msg)

# Wyświetl bilans
st.subheader("Bieżący bilans")

balance = calculate_balance()
st.dataframe(balance)

# dodatkowo w formie listy
st.subheader("Podsumowanie")
for p1 in people:
    for p2 in people:
        if p1 != p2 and balance.loc[p1, p2] > 0:
            st.write(f"{p1} jest winien {p2}: {balance.loc[p1, p2]:.2f} zł")
