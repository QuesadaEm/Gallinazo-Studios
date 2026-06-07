"""Interfaz gráfica del servidor — Sistema de Consulta de ASADAS.

Implementa :class:`VentanaPrincipal`, la ventana Tkinter del equipo central.
Combina en un solo proceso:

* El **MotorConsulta** (persistencia, árbol BST, actualización incremental).
* El **IndiceGeografico** (listas enlazadas geográficas + 3er archivo binario).
* El **Servidor TCP** corriendo en un hilo demonio, que atiende clientes remotos.
* La **GUI** con búsqueda por ID, combos dependientes y visualización en mapa.

Solo el equipo servidor tiene el botón "Actualizar Datos"; los clientes
remotos consultan a través del socket y no pueden modificar los datos.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import List, Optional

from src.api.motor_consulta import MotorConsulta
from src.geografia.generador_mapas import GeneradorMapas
from src.geografia.indice_geografico import IndiceGeografico
from src.modelo.asada import Asada
from src.red.servidor import Servidor


class VentanaPrincipal(tk.Tk):
    """Ventana principal del servidor del sistema de ASADAS.

    :ivar motor: Motor de consulta (persistencia + árbol BST).
    :ivar indice_geo: Índice geográfico jerárquico en memoria.
    :ivar servidor: Servidor TCP que atiende clientes remotos.
    :ivar _cola_log: Cola para enviar mensajes de log desde hilos.
    """

    def __init__(
        self,
        directorio_datos: str = "data",
        host: str = "0.0.0.0",
        port: int = 5000,
        origen_local: Optional[str] = None,
    ) -> None:
        """Inicializa la ventana y todas las dependencias del sistema.

        :param directorio_datos: Carpeta que contiene los archivos binarios.
        :param host: Interfaz de escucha del servidor TCP.
        :param port: Puerto TCP del servidor.
        :param origen_local: Archivo JSON local para modo sin conexión.
        """
        super().__init__()
        self.title("Sistema de Consulta de ASADAS — Servidor")
        self.geometry("900x700")
        self.resizable(True, True)
        self.configure(bg="#f0f4f8")

        self._directorio_datos = directorio_datos
        self._host = host
        self._port = port
        self._origen_local = origen_local

        # Objetos del sistema (se crean en _inicializar_sistema)
        self.motor: Optional[MotorConsulta] = None
        self.indice_geo: IndiceGeografico = IndiceGeografico()
        self.servidor: Optional[Servidor] = None
        self._cola_log: queue.Queue = queue.Queue()
        self._generador_mapas = GeneradorMapas(carpeta_salida="mapas")

        self._construir_ui()
        # Inicializar sistema en hilo para no bloquear la ventana.
        threading.Thread(target=self._inicializar_sistema, daemon=True).start()
        self._procesar_cola_log()

    # ------------------------------------------------------------------ #
    # Construcción de la interfaz                                          #
    # ------------------------------------------------------------------ #

    def _construir_ui(self) -> None:
        """Construye todos los widgets de la ventana."""
        self._construir_barra_superior()
        self._construir_panel_estado()
        self._construir_notebook()
        self._construir_panel_log()

    def _construir_barra_superior(self) -> None:
        """Franja superior con título e información del servidor."""
        barra = tk.Frame(self, bg="#2c3e50", pady=8)
        barra.pack(fill=tk.X)
        tk.Label(
            barra,
            text="Sistema de Consulta de ASADAS de Costa Rica",
            font=("Helvetica", 14, "bold"),
            fg="white",
            bg="#2c3e50",
        ).pack(side=tk.LEFT, padx=16)
        self._lbl_modo = tk.Label(
            barra,
            text="[SERVIDOR]",
            font=("Helvetica", 10, "bold"),
            fg="#2ecc71",
            bg="#2c3e50",
        )
        self._lbl_modo.pack(side=tk.RIGHT, padx=16)

    def _construir_panel_estado(self) -> None:
        """Panel con estado del sistema y botones de acción."""
        panel = tk.Frame(self, bg="#dce6f0", padx=10, pady=6)
        panel.pack(fill=tk.X)

        # Lado izquierdo: información
        izq = tk.Frame(panel, bg="#dce6f0")
        izq.pack(side=tk.LEFT)
        self._lbl_total = tk.Label(izq, text="ASADAS: cargando...", bg="#dce6f0", font=("Helvetica", 9))
        self._lbl_total.pack(side=tk.LEFT, padx=8)
        self._lbl_puerto = tk.Label(izq, text=f"Puerto TCP: {self._port}", bg="#dce6f0", font=("Helvetica", 9))
        self._lbl_puerto.pack(side=tk.LEFT, padx=8)
        fuente_txt = "Fuente: fixture local" if self._origen_local else "Fuente: ARESEP"
        fuente_color = "#e67e22" if self._origen_local else "#27ae60"
        tk.Label(izq, text=fuente_txt, bg="#dce6f0", font=("Helvetica", 9, "bold"), fg=fuente_color).pack(side=tk.LEFT, padx=8)
        self._lbl_estado = tk.Label(izq, text="Estado: inicializando...", bg="#dce6f0", font=("Helvetica", 9))
        self._lbl_estado.pack(side=tk.LEFT, padx=8)

        # Lado derecho: botones
        der = tk.Frame(panel, bg="#dce6f0")
        der.pack(side=tk.RIGHT)
        self._btn_actualizar = ttk.Button(
            der, text="⟳ Actualizar Datos", command=self._actualizar_datos_hilo
        )
        self._btn_actualizar.pack(side=tk.RIGHT, padx=4)
        self._btn_actualizar.state(["disabled"])

    def _construir_notebook(self) -> None:
        """Notebook con las dos pestañas de consulta."""
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        tab1 = tk.Frame(nb, bg="#f8fafc")
        tab2 = tk.Frame(nb, bg="#f8fafc")
        nb.add(tab1, text="  Búsqueda por ID  ")
        nb.add(tab2, text="  Búsqueda Geográfica  ")

        self._construir_tab_id(tab1)
        self._construir_tab_geo(tab2)

    # ---- Tab búsqueda por ID ----------------------------------------- #

    def _construir_tab_id(self, parent: tk.Frame) -> None:
        """Pestaña de búsqueda de ASADA por identificador numérico."""
        # Fila de entrada
        fila = tk.Frame(parent, bg="#f8fafc", pady=12)
        fila.pack(fill=tk.X, padx=20)
        tk.Label(fila, text="ID de ASADA:", bg="#f8fafc", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self._entry_id = ttk.Entry(fila, width=12, font=("Helvetica", 10))
        self._entry_id.pack(side=tk.LEFT, padx=8)
        self._entry_id.bind("<Return>", lambda _: self._buscar_por_id())
        ttk.Button(fila, text="Buscar", command=self._buscar_por_id).pack(side=tk.LEFT)

        # Panel de resultados
        res = tk.LabelFrame(parent, text="Resultado", bg="#f8fafc", padx=10, pady=8, font=("Helvetica", 9, "bold"))
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
        self._asada_encontrada: Optional[Asada] = None

    # ---- Tab búsqueda geográfica ------------------------------------- #

    def _construir_tab_geo(self, parent: tk.Frame) -> None:
        """Pestaña de búsqueda jerárquica por división política."""
        filtros = tk.Frame(parent, bg="#f8fafc", pady=10)
        filtros.pack(fill=tk.X, padx=20)

        # Provincia
        tk.Label(filtros, text="Provincia:", bg="#f8fafc", font=("Helvetica", 9, "bold")).grid(
            row=0, column=0, sticky="w", pady=4
        )
        self._var_provincia = tk.StringVar()
        self._combo_provincia = ttk.Combobox(
            filtros, textvariable=self._var_provincia, state="readonly", width=22
        )
        self._combo_provincia.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        self._combo_provincia.bind("<<ComboboxSelected>>", self._al_elegir_provincia)

        # Cantón
        tk.Label(filtros, text="Cantón:", bg="#f8fafc", font=("Helvetica", 9, "bold")).grid(
            row=0, column=2, sticky="w", pady=4
        )
        self._var_canton = tk.StringVar()
        self._combo_canton = ttk.Combobox(
            filtros, textvariable=self._var_canton, state="readonly", width=22
        )
        self._combo_canton.grid(row=0, column=3, padx=8, pady=4, sticky="w")
        self._combo_canton.bind("<<ComboboxSelected>>", self._al_elegir_canton)

        # Distrito
        tk.Label(filtros, text="Distrito:", bg="#f8fafc", font=("Helvetica", 9, "bold")).grid(
            row=1, column=0, sticky="w", pady=4
        )
        self._var_distrito = tk.StringVar()
        self._combo_distrito = ttk.Combobox(
            filtros, textvariable=self._var_distrito, state="readonly", width=22
        )
        self._combo_distrito.grid(row=1, column=1, padx=8, pady=4, sticky="w")
        self._combo_distrito.bind("<<ComboboxSelected>>", self._al_elegir_distrito)

        ttk.Button(filtros, text="Ver en Mapa", command=self._ver_mapa_geo).grid(
            row=1, column=3, padx=8, pady=4, sticky="w"
        )

        # Lista de ASADAS del distrito
        lista_frame = tk.LabelFrame(
            parent, text="ASADAS del Distrito", bg="#f8fafc", padx=8, pady=6,
            font=("Helvetica", 9, "bold")
        )
        lista_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        cols = ("id", "operador", "tipo_sistema")
        self._tabla_geo = ttk.Treeview(
            lista_frame, columns=cols, show="headings", height=10
        )
        self._tabla_geo.heading("id", text="ID")
        self._tabla_geo.heading("operador", text="Operador")
        self._tabla_geo.heading("tipo_sistema", text="Tipo Sistema")
        self._tabla_geo.column("id", width=60, anchor="center")
        self._tabla_geo.column("operador", width=350)
        self._tabla_geo.column("tipo_sistema", width=160)
        sb = ttk.Scrollbar(lista_frame, orient=tk.VERTICAL, command=self._tabla_geo.yview)
        self._tabla_geo.configure(yscrollcommand=sb.set)
        self._tabla_geo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tabla_geo.bind("<<TreeviewSelect>>", self._al_seleccionar_asada_geo)

        # Detalle de la ASADA seleccionada en la tabla
        self._lbl_detalle_geo = tk.Label(
            parent, text="", bg="#f8fafc", font=("Helvetica", 8),
            justify=tk.LEFT, anchor="w", fg="#555"
        )
        self._lbl_detalle_geo.pack(fill=tk.X, padx=20)
        self._asadas_geo: List[dict] = []

    def _construir_panel_log(self) -> None:
        """Panel inferior con el registro de actividad del servidor."""
        frame = tk.LabelFrame(
            self, text="Registro de Actividad", bg="#f0f4f8",
            padx=6, pady=4, font=("Helvetica", 8, "bold")
        )
        frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self._log = scrolledtext.ScrolledText(
            frame, height=5, state="disabled", font=("Courier", 8),
            bg="#1e1e2e", fg="#a6e3a1", wrap=tk.WORD
        )
        self._log.pack(fill=tk.X)

    # ------------------------------------------------------------------ #
    # Inicialización del sistema en hilo de fondo                         #
    # ------------------------------------------------------------------ #

    def _inicializar_sistema(self) -> None:
        """Carga el motor, construye el índice geográfico y arranca el TCP."""
        try:
            fuente = "fixture local (desarrollo)" if self._origen_local else "ARESEP (datos reales)"
            self._log_msg(f"Inicializando MotorConsulta — fuente: {fuente}...")

            def al_regenerar(repo):
                """Callback: reconstruye el índice geográfico y lo persiste."""
                self.indice_geo.construir(repo)
                ruta_geo = self.motor.ruta_indice_geo
                self.indice_geo.persistir(ruta_geo)
                self._log_msg(f"Índice geográfico reconstruido y persistido en {ruta_geo}")
                self.after(0, self._recargar_combos)

            self.motor = MotorConsulta(
                directorio_datos=self._directorio_datos,
                origen_local=self._origen_local,
                al_regenerar=al_regenerar,
            )
            self.motor.iniciar()

            # Si los datos ya existían el callback no se disparó: construir.
            if not self.indice_geo.provincias():
                ruta_geo = self.motor.ruta_indice_geo
                # Intentar cargar desde el binario antes de recorrer el repo.
                if not self.indice_geo.cargar_desde_binario(ruta_geo):
                    self.indice_geo.construir(self.motor.repositorio)
                    self.indice_geo.persistir(ruta_geo)
                    self._log_msg(f"Índice geográfico construido y persistido.")

            total = self.motor.repositorio.cantidad_registros()
            self._log_msg(f"Sistema listo: {total} ASADAS cargadas.")
            self.after(0, lambda: self._lbl_total.config(text=f"ASADAS: {total}"))
            self.after(0, lambda: self._lbl_estado.config(text="Estado: activo"))
            self.after(0, self._recargar_combos)
            self.after(0, lambda: self._btn_actualizar.state(["!disabled"]))

            # Arrancar servidor TCP
            self.servidor = Servidor(self.motor, self.indice_geo, self._host, self._port)
            self._log_msg(f"Iniciando servidor TCP en {self._host}:{self._port}...")
            threading.Thread(target=self.servidor.iniciar, daemon=True).start()
            self.after(0, lambda: self._lbl_puerto.config(text=f"Puerto TCP: {self._port} ✓"))
            self._log_msg("Servidor TCP activo. Esperando clientes...")

        except Exception as exc:
            self._log_msg(f"ERROR al inicializar: {exc}")
            self.after(0, lambda: self._lbl_estado.config(text=f"Error: {exc}", fg="red"))

    # ------------------------------------------------------------------ #
    # Acciones de los botones                                             #
    # ------------------------------------------------------------------ #

    def _buscar_por_id(self) -> None:
        """Busca una ASADA por su ID usando el árbol BST en memoria."""
        if self.motor is None:
            return
        texto = self._entry_id.get().strip()
        if not texto.isdigit():
            messagebox.showwarning("Entrada inválida", "El ID debe ser un número entero.")
            return
        id_asada = int(texto)
        asada = self.motor.obtener_asada(id_asada)
        if asada is None:
            messagebox.showinfo("No encontrada", f"No existe la ASADA con ID {id_asada}.")
            self._asada_encontrada = None
            self._btn_mapa_id.state(["disabled"])
            for attr in ("_res_id", "_res_operador", "_res_provincia", "_res_canton",
                         "_res_distrito", "_res_tipo", "_res_telefono", "_res_correo",
                         "_res_codigo", "_res_x", "_res_y"):
                getattr(self, attr).set("—")
            return

        self._asada_encontrada = asada
        self._res_id.set(str(asada.id_Asada))
        self._res_operador.set(asada.operador or "—")
        self._res_provincia.set(asada.provincia or "—")
        self._res_canton.set(asada.canton or "—")
        self._res_distrito.set(asada.distrito or "—")
        self._res_tipo.set(asada.tipoSistema or "—")
        self._res_telefono.set(asada.telefono or "—")
        self._res_correo.set(asada.correo or "—")
        self._res_codigo.set(asada.codigoDTA or "—")
        self._res_x.set(f"{asada.coordenadaX:.2f}")
        self._res_y.set(f"{asada.coordenadaY:.2f}")
        self._btn_mapa_id.state(["!disabled"])

    def _ver_mapa_id(self) -> None:
        """Genera y abre el mapa de la ASADA encontrada por ID."""
        if self._asada_encontrada is None:
            return
        try:
            ruta = self._generador_mapas.generar_html(
                [self._asada_encontrada], nombre_archivo="detalle_id.html"
            )
            GeneradorMapas.abrir_en_navegador(ruta)
            self._log_msg(f"Mapa abierto: {ruta}")
        except Exception as exc:
            messagebox.showerror("Error al generar mapa", str(exc))

    def _actualizar_datos_hilo(self) -> None:
        """Lanza la actualización incremental en un hilo de fondo."""
        if self.motor is None:
            return
        self._btn_actualizar.state(["disabled"])
        self._log_msg("Iniciando actualización incremental desde ARESEP...")
        threading.Thread(target=self._actualizar_datos, daemon=True).start()

    def _actualizar_datos(self) -> None:
        """Sincroniza con ARESEP y actualiza el índice geográfico."""
        try:
            hubo_cambios = self.motor.actualizar_datos()
            if hubo_cambios:
                total = self.motor.repositorio.cantidad_registros()
                self._log_msg(f"Actualización completada: {total} ASADAS.")
                self.after(0, lambda: self._lbl_total.config(text=f"ASADAS: {total}"))
            else:
                self._log_msg("Los datos ya están actualizados (sin cambios remotos).")
        except Exception as exc:
            self._log_msg(f"Error durante la actualización: {exc}")
        finally:
            self.after(0, lambda: self._btn_actualizar.state(["!disabled"]))

    def _ver_mapa_geo(self) -> None:
        """Genera el mapa con las ASADAS del distrito seleccionado."""
        if not self._asadas_geo:
            messagebox.showinfo("Sin datos", "Primero seleccione una provincia, cantón y distrito.")
            return
        try:
            asadas = [Asada.desde_dict(r) for r in self._asadas_geo]
            prov = self._var_provincia.get()
            cant = self._var_canton.get()
            dist = self._var_distrito.get()
            nombre = f"geo_{prov}_{cant}_{dist}.html".replace(" ", "_")
            ruta = self._generador_mapas.generar_html(asadas, nombre_archivo=nombre)
            GeneradorMapas.abrir_en_navegador(ruta)
            self._log_msg(f"Mapa geográfico abierto: {ruta}")
        except Exception as exc:
            messagebox.showerror("Error al generar mapa", str(exc))

    # ------------------------------------------------------------------ #
    # Combos dependientes                                                 #
    # ------------------------------------------------------------------ #

    def _recargar_combos(self) -> None:
        """Llena el combo de provincias con los datos del índice geográfico."""
        provincias = self.indice_geo.provincias()
        self._combo_provincia["values"] = provincias
        self._combo_canton["values"] = []
        self._combo_distrito["values"] = []
        self._var_provincia.set("")
        self._var_canton.set("")
        self._var_distrito.set("")

    def _al_elegir_provincia(self, _event=None) -> None:
        """Carga los cantones de la provincia seleccionada."""
        prov = self._var_provincia.get()
        cantones = self.indice_geo.cantones_de(prov)
        self._combo_canton["values"] = cantones
        self._combo_distrito["values"] = []
        self._var_canton.set("")
        self._var_distrito.set("")
        self._tabla_geo.delete(*self._tabla_geo.get_children())
        self._asadas_geo = []
        self._lbl_detalle_geo.config(text="")

    def _al_elegir_canton(self, _event=None) -> None:
        """Carga los distritos del cantón seleccionado."""
        prov = self._var_provincia.get()
        cant = self._var_canton.get()
        distritos = self.indice_geo.distritos_de(prov, cant)
        self._combo_distrito["values"] = distritos
        self._var_distrito.set("")
        self._tabla_geo.delete(*self._tabla_geo.get_children())
        self._asadas_geo = []
        self._lbl_detalle_geo.config(text="")

    def _al_elegir_distrito(self, _event=None) -> None:
        """Carga las ASADAS del distrito seleccionado en la tabla."""
        if self.motor is None:
            return
        prov = self._var_provincia.get()
        cant = self._var_canton.get()
        dist = self._var_distrito.get()
        pares = self.indice_geo.asadas_de(prov, cant, dist)
        # Leer registros completos desde el archivo binario principal.
        asadas = []
        for id_asada, posicion in sorted(pares, key=lambda p: p[0]):
            try:
                asada = self.motor.repositorio.leer_registro(posicion)
                asadas.append(asada.a_dict())
            except (ValueError, OSError):
                pass
        self._asadas_geo = asadas
        self._tabla_geo.delete(*self._tabla_geo.get_children())
        for r in asadas:
            self._tabla_geo.insert("", "end", values=(
                r.get("id_Asada", ""), r.get("operador", ""), r.get("tipoSistema", "")
            ))
        self._lbl_detalle_geo.config(
            text=f"{len(asadas)} ASADA(s) en {prov} › {cant} › {dist}"
        )

    def _al_seleccionar_asada_geo(self, _event=None) -> None:
        """Muestra el detalle de la ASADA seleccionada en la tabla geográfica."""
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
            f"Tipo: {r.get('tipoSistema')}  |  Coord X: {r.get('coordenadaX'):.2f}  "
            f"Y: {r.get('coordenadaY'):.2f}"
        )
        self._lbl_detalle_geo.config(text=texto)

    # ------------------------------------------------------------------ #
    # Sistema de log thread-safe                                          #
    # ------------------------------------------------------------------ #

    def _log_msg(self, mensaje: str) -> None:
        """Encola un mensaje de log desde cualquier hilo."""
        self._cola_log.put(mensaje)

    def _procesar_cola_log(self) -> None:
        """Vacía la cola de log y escribe los mensajes en el widget."""
        while not self._cola_log.empty():
            msg = self._cola_log.get_nowait()
            self._log.config(state="normal")
            self._log.insert(tk.END, msg + "\n")
            self._log.see(tk.END)
            self._log.config(state="disabled")
        # Reprogramar cada 200 ms para no saturar la event loop.
        self.after(200, self._procesar_cola_log)

    # ------------------------------------------------------------------ #
    # Cierre limpio                                                        #
    # ------------------------------------------------------------------ #

    def on_closing(self) -> None:
        """Detiene el servidor TCP antes de cerrar la ventana."""
        if self.servidor is not None:
            self.servidor.detener()
        self.destroy()
