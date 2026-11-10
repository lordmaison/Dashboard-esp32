    # ==========================================
    # EXPORTACIÓN DE DATOS CSV
    # ==========================================

    if not df.empty:
        csv = df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="📥 Descargar datos CSV",
            data=csv,
            file_name="registro_temperaturas.csv",
            mime="text/csv",
            key="descargar_csv",
        )
    else:
        st.button(
            "📥 Descargar datos CSV",
            disabled=True,
            key="descargar_csv_vacio",
        )
