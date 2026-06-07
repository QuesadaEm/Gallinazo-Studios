"""Interfaz gráfica del cliente remoto — Sistema de Consulta de ASADAS.

Implementa :class:`VentanaCliente`, la ventana Tkinter del equipo cliente.
Consulta al servidor a través del socket TCP usando :class:`~src.red.cliente.Cliente`.

El cliente es de **solo lectura**: puede buscar por ID y navegar la jerarquía
geográfica, pero no puede actualizar los datos del sistema.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import List, Optional

from src.geografia.generador_mapas import GeneradorMapas
from src.modelo.asada import Asada
from src.red.cliente import Cliente, ErrorConsulta


class VentanaCliente(tk.Tk):
    """Ventana de consulta remota del sistema de ASADAS.

    Se conecta al servidor TCP y realiza todas las consultas a través del
    protocolo de sockets, sin acceso directo a los archivos binarios.

    :ivar _cliente: Instancia del cliente TCP (None cuando está desconectado).
    """

    def __init__(self) -> None:
        """Inicializa la ventana del cliente."""
        super().__init__()
        self.title("Sistema de Consulta de ASADAS — Cliente Remoto")
        self.geometry("860x660")
        self.resizable(True, True)
        self.configure(bg="#f0f4f8")

        self._cliente: Optional[Cliente] = None
        self._generador_mapas = GeneradorMapas(carpeta_salida="mapas")
        self._asada_encontrada: Optional[Asada] = None
        self._asadas_geo: List[dict] = []

        self._construir_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ------------------------------------------------------------------ #
    # Construcción de la interfaz                                          #
    # ------------------------------------------------------------------ #

    def _construir_ui(self) -> None:
        self._construir_barra_superior()
        self._construir_panel_conexion()
        self._construir_notebook()
        self._construir_panel_log()

    def _construir_barra_superior(self) -> None:
        barra = tk.Frame(self, bg="#1a252f", pady=8)
        barra.pack(fill=tk.X)
        tk.Label(
            barra,
            text="Sistema de Consulta de ASADAS de Costa Rica",
            font=("Helvetica", 14, "bold"),
            fg="white",
            bg="#1a252f",
        ).pack(side=tk.LEFT, padx=16)
        self._lbl_modo = tk.Label(
            barra, text="[CLIENTE REMOTO]", font=("Helvetica", 10, "bold"),
            fg="#f39c12", bg="#1a252f",
        )
        self._lbl_modo.pack(side=tk.RIGHT, padx=16)

    def _construir_panel_conexion(self) -> None:
        """Panel de conexión al servidor TCP."""
        panel = tk.Frame(self, bg="#d5e8f0", padx=10, pady=6)
        panel.pack(fill=tk.X)

        tk.Label(panel, text="Servidor:", bg="#d5e8f0", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT)
        self._entry_host = ttk.Entry(panel, width=16, font=("Helvetica", 9))
        self._entry_host.insert(0, "127.0.0.1")
        self._entry_host.pack(side=tk.LEFT, padx=4)

        tk.Label(panel, text="Puerto:", bg="#d5e8f0", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT)
        self._entry_port = ttk.Entry(panel, width=7, font=("Helvetica", 9))
        self._entry_port.insert(0, "5000")
        self._entry_port.pack(side=tk.LEFT, padx=4)

        self._btn_conectar = ttk.Button(panel, text="Conectar", command=self._conectar)
        self._btn_conectar.pack(side=tk.LEFT, padx=8)
        self._btn_desconectar = ttk.Button(
            panel, text="Desconectar", command=self._desconectar, state="disabled"
        )
        self._btn_desconectar.pack(side=tk.LEFT)

        self._lbl_conexion = tk.Label(
            panel, text="Desconectado", bg="#d5e8f0",
            font=("Helvetica", 9), fg="#e74c3c"
        )
        self._lbl_conexion.pack(side=tk.RIGHT, padx=10)

    def _construir_notebook(self) -> None:
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        tab1 = tk.Frame(self._nb, bg="#f8fafc")
        tab2 = tk.Frame(self._nb, bg="#f8fafc")
        self._nb.add(tab1, text="  Búsqueda por ID  ")
        self._nb.add(tab2, text="  Búsqueda Geográfica  ")

        self._construir_tab_id(tab1)
        self._construir_tab_geo(tab2)

    # ---- Tab búsqueda por ID ----------------------------------------- #

    def _construir_tab_id(self, parent: tk.Frame) -> None:
        fila = tk.Frame(parent, bg="#f8fafc", pady=12)
        fila.pack(fill=tk.X, padx=20)
        tk.Label(fila, text="ID de ASADA:", bg="#f8fafc", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self._entry_id = ttk.Entry(fila, width=12, font=("Helvetica", 10))
        self._entry_id.pack(side=tk.LEFT, padx=8)
        self._entry_id.bind("<Return>", lambda _: self._buscar_por_id())
        self._btn_buscar_id = ttk.Button(fila, text="Buscar", command=self._buscar_por_id, state="disabled")
        self._btn_buscar_id.pack(side=tk.LEFT)

        res = tk.LabelFrame(
            parent, text="Resultado", bg="#f8fafc", padx=10, pady=8,
            font=("Helvetica", 9, "bold")
        )
        res.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        campos = [
            ("ID:", "_res_id"), ("Operador:", "_res_operador"),
            ("Provincia:", "_res_provincia"), ("Cantón:", "_res_canton"),
            ("Distrito:", "_res_distrito"), ("Tipo sistema:", "_res_tipo"),
            ("Teléfono:", "_res_telefono"), ("Correo:", "_res_correo"),
            ("CódigoDTA:", "_res_codigo"), ("CoordX (CRTM05):", "_res_x"),
            ("CoordY (CRTM05):", "_res_y"),
        ]
        for fila_idx, (etiqueta, attr) in enumerate(campos):
            r = fila_idx // 2
            c = (fila_idx % 2) * 2
            tk.Label(res, text=etiqueta, bg="#f8fafc", font=("Helvetica", 9, "bold"), anchor="e").grid(
                row=r, column=c, sticky="e", padx=(10, 4), pady=2
            )
            var = tk.StringVar(value="—")
            setattr(self, attr, var)
            tk.Label(res, textvariable=var, bg="#f8fafc", font=("Helvetica", 9), anchor="w").grid(
                row=r, column=c + 1, sticky="w", padx=(0, 20), pady=2
            )

        self._btn_mapa_id = ttk.Button(
            parent, text="Ver en Mapa", state="disabled", command=self._ver_mapa_id
        )
        self._btn_mapa_id.pack(pady=6)

    # ---- Tab búsqueda geográfica ------------------------------------- #

    def _construir_tab_geo(self, parent: tk.Frame) -> None:
        filtros = tk.Frame(parent, bg="#f8fafc", pady=10)
        filtros.pack(fill=tk.X, padx=20)

        tk.Label(filtros, text="Provincia:", bg="#f8fafc", font=("Helvetica", 9, "bold")).grid(
            row=0, column=0, sticky="w", pady=4
        )
        self._var_provincia = tk.StringVar()
        self._combo_provincia = ttk.Combobox(
            filtros, textvariable=self._var_provincia, state="disabled", width=22
        )
        self._combo_provincia.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        self._combo_provincia.bind("<<ComboboxSelected>>", self._al_elegir_provincia)

        tk.Label(filtros, text="Cantón:", bg="#f8fafc", font=("Helvetica", 9, "bold")).grid(
            row=0, column=2, sticky="w", pady=4
        )
        self._var_canton = tk.StringVar()
        self._combo_canton = ttk.Combobox(
            filtros, textvariable=self._var_canton, state="disabled", width=22
        )
        self._combo_canton.grid(row=0, column=3, padx=8, pady=4, sticky="w")
        self._combo_canton.bind("<<ComboboxSelected>>", self._al_elegir_canton)

        tk.Label(filtros, text="Distrito:", bg="#f8fafc", font=("Helvetica", 9, "bold")).grid(
            row=1, column=0, sticky="w", pady=4
        )
        self._var_distrito = tk.StringVar()
        self._combo_distrito = ttk.Combobox(
            filtros, textvariable=self._var_distrito, state="disabled", width=22
        )
        self._combo_distrito.grid(row=1, column=1, padx=8, pady=4, sticky="w")
        self._combo_distrito.bind("<<ComboboxSelected>>", self._al_elegir_distrito)

        self._btn_mapa_geo = ttk.Button(
            filtros, text="Ver en Mapa", command=self._ver_mapa_geo, state="disabled"
        )
        self._btn_mapa_geo.grid(row=1, column=3, padx=8, pady=4, sticky="w")

        lista_frame = tk.LabelFrame(
            parent, text="ASADAS del Distrito", bg="#f8fafc", padx=8, pady=6,
            font=("Helvetica", 9, "bold")
        )
        lista_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        cols = ("id", "operador", "tipo_sistema")
        self._tabla_geo = ttk.Treeview(lista_frame, columns=cols, show="headings", height=10)
        self._tabla_geo.heading("id", text="ID")
        self._tabla_geo.heading("operador", text="Operador")
        self._tabla_geo.heading("tipo_sistema", text="Tipo Sistema")
        self._tabla_geo.column("id", width=60, anchor="center")
        self._tabla_geo.column("operador", width=340)
        self._tabla_geo.column("tipo_sistema", width=160)
        sb = ttk.Scrollbar(lista_frame, orient=tk.VERTICAL, command=self._tabla_geo.yview)
        self._tabla_geo.configure(yscrollcommand=sb.set)
        self._tabla_geo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tabla_geo.bind("<<TreeviewSelect>>", self._al_seleccionar_asada_geo)

        self._lbl_detalle_geo = tk.Label(
            parent, text="", bg="#f8fafc", font=("Helvetica", 8),
            justify=tk.LEFT, anchor="w", fg="#555"
        )
        self._lbl_detalle_geo.pack(fill=tk.X, padx=20)

    def _construir_panel_log(self) -> None:
        frame = tk.LabelFrame(
            self, text="Registro de Actividad", bg="#f0f4f8",
            padx=6, pady=4, font=("Helvetica", 8, "bold")
        )
        frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self._log = scrolledtext.ScrolledText(
            frame, height=5, state="disabled", font=("Courier", 8),
            bg="#1e1e2e", fg="#89b4fa", wrap=tk.WORD
        )
        self._log.pack(fill=tk.X)

    # ------------------------------------------------------------------ #
    # Conexión / desconexión                                              #
    # ------------------------------------------------------------------ #

    def _conectar(self) -> None:
        """Establece conexión con el servidor y carga las provincias."""
        host = self._entry_host.get().strip()
        try:
            port = int(self._entry_port.get().strip())
        except ValueError:
            messagebox.showwarning("Puerto inválido", "El puerto debe ser un número entero.")
            return

        try:
            cliente = Cliente(host, port)
            cliente.conectar()
            self._cliente = cliente
            self._log_msg(f"Conectado a {host}:{port}")
            self._lbl_conexion.config(text=f"Conectado a {host}:{port}", fg="#2ecc71")
            self._btn_conectar.config(state="disabled")
            self._btn_desconectar.config(state="normal")
            self._btn_buscar_id.config(state="normal")
            self._btn_mapa_geo.config(state="normal")
            self._cargar_provincias()
        except OSError as exc:
            messagebox.showerror("Error de conexión", f"No se pudo conectar:\n{exc}")

    def _desconectar(self) -> None:
        """Cierra la conexión con el servidor."""
        if self._cliente is not None:
            self._cliente.cerrar()
            self._cliente = None
        self._lbl_conexion.config(text="Desconectado", fg="#e74c3c")
        self._btn_conectar.config(state="normal")
        self._btn_desconectar.config(state="disabled")
        self._btn_buscar_id.config(state="disabled")
        self._combo_provincia.config(state="disabled")
        self._combo_canton.config(state="disabled")
        self._combo_distrito.config(state="disabled")
        self._btn_mapa_geo.config(state="disabled")
        self._log_msg("Desconectado del servidor.")

    def _cargar_provincias(self) -> None:
        """Consulta al servidor la lista de provincias disponibles."""
        if self._cliente is None:
            return
        try:
            provincias = self._cliente.provincias()
            self._combo_provincia["values"] = provincias
            self._combo_provincia.config(state="readonly")
            self._combo_canton.config(state="disabled")
            self._combo_distrito.config(state="disabled")
            self._var_provincia.set("")
            self._var_canton.set("")
            self._var_distrito.set("")
            self._log_msg(f"Provincias recibidas: {len(provincias)}")
        except ErrorConsulta as exc:
            self._log_msg(f"Error al cargar provincias: {exc}")

    # ------------------------------------------------------------------ #
    # Búsqueda por ID                                                     #
    # ------------------------------------------------------------------ #

    def _buscar_por_id(self) -> None:
        """Consulta al servidor la ASADA con el ID indicado."""
        if self._cliente is None:
            return
        texto = self._entry_id.get().strip()
        if not texto.isdigit():
            messagebox.showwarning("Entrada inválida", "El ID debe ser un número entero.")
            return
        try:
            r = self._cliente.por_id(int(texto))
            self._asada_encontrada = Asada.desde_dict(r)
            self._res_id.set(str(r.get("id_Asada", "—")))
            self._res_operador.set(r.get("operador") or "—")
            self._res_provincia.set(r.get("provincia") or "—")
            self._res_canton.set(r.get("canton") or "—")
            self._res_distrito.set(r.get("distrito") or "—")
            self._res_tipo.set(r.get("tipoSistema") or "—")
            self._res_telefono.set(r.get("telefono") or "—")
            self._res_correo.set(r.get("correo") or "—")
            self._res_codigo.set(r.get("codigoDTA") or "—")
            self._res_x.set(f"{r.get('coordenadaX', 0):.2f}")
            self._res_y.set(f"{r.get('coordenadaY', 0):.2f}")
            self._btn_mapa_id.config(state="normal")
        except ErrorConsulta as exc:
            messagebox.showinfo("No encontrada", str(exc))
            self._asada_encontrada = None
            self._btn_mapa_id.config(state="disabled")

    def _ver_mapa_id(self) -> None:
        if self._asada_encontrada is None:
            return
        try:
            ruta = self._generador_mapas.generar_html(
                [self._asada_encontrada], nombre_archivo="cliente_id.html"
            )
            GeneradorMapas.abrir_en_navegador(ruta)
            self._log_msg(f"Mapa abierto: {ruta}")
        except Exception as exc:
            messagebox.showerror("Error al generar mapa", str(exc))

    # ------------------------------------------------------------------ #
    # Combos dependientes (consultas al servidor)                         #
    # ------------------------------------------------------------------ #

    def _al_elegir_provincia(self, _event=None) -> None:
        """Consulta los cantones de la provincia al servidor."""
        if self._cliente is None:
            return
        prov = self._var_provincia.get()
        try:
            cantones = self._cliente.cantones(prov)
            self._combo_canton["values"] = cantones
            self._combo_canton.config(state="readonly")
            self._combo_distrito.config(state="disabled")
            self._combo_distrito["values"] = []
            self._var_canton.set("")
            self._var_distrito.set("")
            self._tabla_geo.delete(*self._tabla_geo.get_children())
            self._asadas_geo = []
            self._lbl_detalle_geo.config(text="")
        except ErrorConsulta as exc:
            self._log_msg(f"Error al cargar cantones: {exc}")

    def _al_elegir_canton(self, _event=None) -> None:
        """Consulta los distritos del cantón al servidor."""
        if self._cliente is None:
            return
        prov = self._var_provincia.get()
        cant = self._var_canton.get()
        try:
            distritos = self._cliente.distritos(prov, cant)
            self._combo_distrito["values"] = distritos
            self._combo_distrito.config(state="readonly")
            self._var_distrito.set("")
            self._tabla_geo.delete(*self._tabla_geo.get_children())
            self._asadas_geo = []
            self._lbl_detalle_geo.config(text="")
        except ErrorConsulta as exc:
            self._log_msg(f"Error al cargar distritos: {exc}")

    def _al_elegir_distrito(self, _event=None) -> None:
        """Consulta las ASADAS del distrito al servidor."""
        if self._cliente is None:
            return
        prov = self._var_provincia.get()
        cant = self._var_canton.get()
        dist = self._var_distrito.get()
        try:
            registros = self._cliente.asadas(prov, cant, dist)
            self._asadas_geo = sorted(registros, key=lambda r: r.get("id_Asada", 0))
            self._tabla_geo.delete(*self._tabla_geo.get_children())
            for r in self._asadas_geo:
                self._tabla_geo.insert("", "end", values=(
                    r.get("id_Asada", ""), r.get("operador", ""), r.get("tipoSistema", "")
                ))
            self._lbl_detalle_geo.config(
                text=f"{len(self._asadas_geo)} ASADA(s) en {prov} › {cant} › {dist}"
            )
        except ErrorConsulta as exc:
            self._log_msg(f"Error al cargar ASADAS: {exc}")

    def _al_seleccionar_asada_geo(self, _event=None) -> None:
        seleccion = self._tabla_geo.selection()
        if not seleccion:
            return
        fila = self._tabla_geo.index(seleccion[0])
        if fila >= len(self._asadas_geo):
            return
        r = self._asadas_geo[fila]
        texto = (
            f"ID: {r.get('id_Asada')}  |  Operador: {r.get('operador')}  |  "
            f"Teléfono: {r.get('telefono') or '—'}  |  Correo: {r.get('correo') or '—'}  |  "
            f"Tipo: {r.get('tipoSistema')}  |  "
            f"Coord X: {r.get('coordenadaX', 0):.2f}  Y: {r.get('coordenadaY', 0):.2f}"
        )
        self._lbl_detalle_geo.config(text=texto)

    def _ver_mapa_geo(self) -> None:
        if not self._asadas_geo:
            messagebox.showinfo("Sin datos", "Primero seleccione una provincia, cantón y distrito.")
            return
        try:
            asadas = [Asada.desde_dict(r) for r in self._asadas_geo]
            prov = self._var_provincia.get()
            cant = self._var_canton.get()
            dist = self._var_distrito.get()
            nombre = f"cli_geo_{prov}_{cant}_{dist}.html".replace(" ", "_")
            ruta = self._generador_mapas.generar_html(asadas, nombre_archivo=nombre)
            GeneradorMapas.abrir_en_navegador(ruta)
            self._log_msg(f"Mapa abierto: {ruta}")
        except Exception as exc:
            messagebox.showerror("Error al generar mapa", str(exc))

    # ------------------------------------------------------------------ #
    # Log y cierre                                                        #
    # ------------------------------------------------------------------ #

    def _log_msg(self, mensaje: str) -> None:
        self._log.config(state="normal")
        self._log.insert(tk.END, mensaje + "\n")
        self._log.see(tk.END)
        self._log.config(state="disabled")

    def on_closing(self) -> None:
        if self._cliente is not None:
            self._cliente.cerrar()
        self.destroy()
