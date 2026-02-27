import streamlit as st
import simpy
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
import plotly.express as px
import plotly.graph_objects as go


# ============================
# KONFIGURASI SIMULASI
# ============================
@dataclass
class Config:
    NUM_MEJA: int = 60
    MAHASISWA_PER_MEJA: int = 3
    TOTAL_PETUGAS: int = 10

    TARGET_DURATION: int = 1800   # 30 menit (1800 detik)

    START_HOUR: int = 7
    START_MINUTE: int = 0

    RANDOM_SEED: int = 42


# ============================
# MODEL SIMULASI PIKET DES
# ============================
class PiketDES:
    def __init__(self, config: Config):
        self.config = config
        self.env = simpy.Environment()

        self.total_ompreng = config.NUM_MEJA * config.MAHASISWA_PER_MEJA

        # Distribusi petugas (proporsional)
        lauk = max(1, int(config.TOTAL_PETUGAS * 0.4))
        angkut = max(1, int(config.TOTAL_PETUGAS * 0.3))
        nasi = max(1, config.TOTAL_PETUGAS - lauk - angkut)

        self.petugas_lauk = simpy.Resource(self.env, capacity=lauk)
        self.petugas_angkut = simpy.Resource(self.env, capacity=angkut)
        self.petugas_nasi = simpy.Resource(self.env, capacity=nasi)

        self.store_lauk = simpy.Store(self.env)
        self.store_meja = simpy.Store(self.env)

        # Base time agar total mendekati 30 menit
        self.base_time = config.TARGET_DURATION / self.total_ompreng

        self.start_time = datetime(2024, 1, 1, config.START_HOUR, config.START_MINUTE)

        random.seed(config.RANDOM_SEED)
        np.random.seed(config.RANDOM_SEED)

        self.data = []

    def rand_time(self):
        return random.uniform(self.base_time * 0.8, self.base_time * 1.2)

    def to_clock(self, sec):
        return self.start_time + timedelta(seconds=sec)

    def proses_lauk(self, i):
        with self.petugas_lauk.request() as req:
            yield req
            yield self.env.timeout(self.rand_time() * 0.3)
            yield self.store_lauk.put((i, self.env.now))

    def proses_angkut(self):
        selesai = 0
        while selesai < self.total_ompreng:
            item = yield self.store_lauk.get()
            with self.petugas_angkut.request() as req:
                yield req
                yield self.env.timeout(self.rand_time() * 0.3)
                yield self.store_meja.put((item[0], item[1], self.env.now))
                selesai += 1

    def proses_nasi(self):
        selesai = 0
        while selesai < self.total_ompreng:
            om = yield self.store_meja.get()
            with self.petugas_nasi.request() as req:
                yield req
                yield self.env.timeout(self.rand_time() * 0.4)

                self.data.append({
                    "id": om[0],
                    "selesai_lauk": om[1],
                    "selesai_angkut": om[2],
                    "selesai_nasi": self.env.now,
                    "jam_selesai": self.to_clock(self.env.now)
                })
                selesai += 1

    def run(self):
        for i in range(self.total_ompreng):
            self.env.process(self.proses_lauk(i))

        self.env.process(self.proses_angkut())
        self.env.process(self.proses_nasi())

        self.env.run()
        return self.analyze_results()

    def analyze_results(self):
        df = pd.DataFrame(self.data)

        total_time = df["selesai_nasi"].max()
        avg_time = df["selesai_nasi"].mean()

        results = {
            "total_ompreng": self.total_ompreng,
            "durasi_total_detik": total_time,
            "durasi_total_menit": total_time / 60,
            "rata_rata_selesai": avg_time / 60,
            "jam_selesai": self.to_clock(total_time)
        }

        return results, df


# ============================
# VISUALISASI
# ============================
def create_histogram(df):
    fig = px.histogram(
        df,
        x="selesai_nasi",
        nbins=30,
        title="Distribusi Waktu Penyelesaian (detik)",
        color_discrete_sequence=["#1f77b4"]
    )
    return fig


def create_progress_chart(df):
    df_sorted = df.sort_values("selesai_nasi")
    fig = px.line(
        x=df_sorted["selesai_nasi"],
        y=np.arange(len(df_sorted)),
        title="Progress Penyelesaian Ompreng"
    )
    return fig


def create_boxplot(df):
    fig = go.Figure()
    fig.add_trace(go.Box(
        y=df["selesai_nasi"] / 60,
        name="Waktu Selesai (menit)",
        boxpoints="outliers"
    ))
    fig.update_layout(title="Boxplot Waktu Penyelesaian")
    return fig


# ============================
# STREAMLIT APP
# ============================
def main():
    st.set_page_config(
        page_title="Simulasi Piket 30 Menit",
        page_icon="⏱️",
        layout="wide"
    )

    st.title("⏱️ Simulasi Sistem Piket IT Del (Target 30 Menit)")

    with st.sidebar:
        st.subheader("⚙️ Parameter Simulasi")

        num_meja = st.number_input("Jumlah Meja", 10, 200, 60)
        mhs_per_meja = st.number_input("Mahasiswa per Meja", 1, 5, 3)
        total_petugas = st.slider("Jumlah Petugas", 3, 30, 10)

        start_hour = st.slider("Jam Mulai", 0, 23, 7)
        start_minute = st.slider("Menit Mulai", 0, 59, 0)

        run_sim = st.button("🚀 Jalankan Simulasi 30 Menit", use_container_width=True)

    if run_sim:
        with st.spinner("Menjalankan simulasi..."):
            config = Config(
                NUM_MEJA=num_meja,
                MAHASISWA_PER_MEJA=mhs_per_meja,
                TOTAL_PETUGAS=total_petugas,
                START_HOUR=start_hour,
                START_MINUTE=start_minute
            )

            model = PiketDES(config)
            results, df = model.run()

        st.success("Simulasi selesai ✅")

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Ompreng", results["total_ompreng"])
        col2.metric("Durasi Total (menit)", f"{results['durasi_total_menit']:.2f}")
        col3.metric("Selesai Pukul", results["jam_selesai"].strftime("%H:%M:%S"))

        st.markdown("---")
        st.header("📊 Visualisasi")

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(create_histogram(df), use_container_width=True)
        with col2:
            st.plotly_chart(create_progress_chart(df), use_container_width=True)

        st.plotly_chart(create_boxplot(df), use_container_width=True)

        st.markdown("---")
        st.subheader("📄 Data Simulasi")
        st.dataframe(df, use_container_width=True)

    else:
        st.info("Atur parameter lalu klik 'Jalankan Simulasi 30 Menit'.")

    st.markdown("---")
    st.caption("MODSIM – Discrete Event Simulation | Target 30 Menit")


if __name__ == "__main__":
    main()