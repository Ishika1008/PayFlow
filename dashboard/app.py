import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="PayFlow Dashboard", page_icon="💳", layout="wide")
st.title("💳 PayFlow: Payment Transaction Monitor")
st.caption("Simulated transactions with synthetic data. No real payments or card details.")


def fetch_transactions():
    """Fetch all transactions by paging through the API (max 200 per request)."""
    rows, skip = [], 0
    while True:
        r = httpx.get(f"{API_URL}/transactions", params={"skip": skip, "limit": 200}, timeout=10)
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < 200:
            return rows
        skip += 200


# ---------- Sidebar: create test data ----------
st.sidebar.header("Create transaction")
with st.sidebar.form("create_form"):
    customer_id = st.text_input("Customer ID", "cust_001")
    amount = st.number_input("Amount", min_value=0.01, max_value=100000.0, value=49.99)
    currency = st.selectbox("Currency", ["USD", "INR", "EUR", "GBP"])
    submitted = st.form_submit_button("Submit payment")

if submitted:
    try:
        r = httpx.post(
            f"{API_URL}/transactions",
            json={"customer_id": customer_id, "amount": amount, "currency": currency},
            timeout=10,
        )
        if r.status_code == 201:
            st.sidebar.success(f"Status: {r.json()['status']}")
        else:
            st.sidebar.error(r.text)
    except httpx.HTTPError as e:
        st.sidebar.error(f"API error: {e}")

if st.sidebar.button("Generate 20 sample transactions"):
    import random
    for i in range(20):
        httpx.post(
            f"{API_URL}/transactions",
            json={
                "customer_id": f"cust_{random.randint(1, 8):03d}",
                "amount": round(random.uniform(5, 500), 2),
                "currency": random.choice(["USD", "INR", "EUR"]),
            },
            timeout=10,
        )
    st.sidebar.success("Added 20 transactions")

# ---------- Load data ----------
try:
    data = fetch_transactions()
except httpx.HTTPError:
    st.error("Cannot reach the API. Start it with: uvicorn app.main:app --reload")
    st.stop()

if not data:
    st.info("No transactions yet. Use the sidebar to create some.")
    st.stop()

df = pd.DataFrame(data)
df["created_at"] = pd.to_datetime(df["created_at"])

# ---------- Metrics ----------
total = len(df)
success = int((df["status"] == "success").sum())
failed = int((df["status"] == "failed").sum())
rate = success / total * 100

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total transactions", total)
c2.metric("Successful", success)
c3.metric("Failed", failed)
c4.metric("Success rate", f"{rate:.1f}%")

# ---------- Charts ----------
left, right = st.columns(2)

with left:
    st.subheader("Status breakdown")
    status_counts = df["status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    st.plotly_chart(px.pie(status_counts, names="status", values="count", hole=0.4), use_container_width=True)

with right:
    st.subheader("Failure reasons")
    failures = df[df["status"] == "failed"]
    if failures.empty:
        st.write("No failures.")
    else:
        reasons = failures["failure_reason"].value_counts().reset_index()
        reasons.columns = ["reason", "count"]
        st.plotly_chart(px.bar(reasons, x="reason", y="count"), use_container_width=True)

st.subheader("Transactions over time")
timeline = df.set_index("created_at").resample("1min")["id"].count().reset_index()
timeline.columns = ["time", "transactions"]
st.plotly_chart(px.line(timeline, x="time", y="transactions"), use_container_width=True)

# ---------- Table ----------
st.subheader("Transactions")
status_filter = st.selectbox("Filter by status", ["all", "success", "failed", "pending"])
search = st.text_input("Search by customer ID or transaction ID")

view = df if status_filter == "all" else df[df["status"] == status_filter]
if search:
    mask = view["customer_id"].str.contains(search, case=False) | view["transaction_id"].str.contains(search, case=False)
    view = view[mask]

st.dataframe(
    view[["transaction_id", "customer_id", "amount", "currency", "status", "failure_reason", "retry_count", "created_at"]],
    use_container_width=True,
    hide_index=True,
)

# ---------- Retry ----------
st.subheader("Retry a failed payment")
retryable = df[(df["status"] == "failed") & (df["retry_count"] < 3)]
if retryable.empty:
    st.write("No retryable transactions.")
else:
    choice = st.selectbox("Select transaction", retryable["transaction_id"])
    if st.button("Retry payment"):
        r = httpx.post(f"{API_URL}/transactions/{choice}/retry", timeout=10)
        if r.status_code == 200:
            st.success(f"Result: {r.json()['status']}")
            st.rerun()
        else:
            st.error(r.json().get("detail", r.text))