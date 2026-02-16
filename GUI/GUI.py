#!/usr/bin/env python3
"""
Minimal GUI tweaks:
- remove 'examples' column from entity table
- remove title next to banner, give banner more horizontal space
Other logic unchanged.
"""
import copy
import sys
import os
import threading
import time
from pathlib import Path

from anonymization_functions import anonymize_texts
from GUI.text_content import JSON_EXAMPLE, LEGEND, METRICS_EXPLAINATION

# make project root importable (adjust as in your project)
PROJECT_ROOT = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk

from config import DEFAULT_ENTITIES, DEFAULT_EXTRA_PER_MATCHING_LEVEL, DEFAULT_OUTPUTS_IN_SINGLE_FILE,MULTI_PROCESSING, P_CORES
from data_generation import ANONYMIZATION_LABELS
from utils.anonymization_utils import read_file, save_many_texts, save_metrics


# --------------------
#   Entity metadata
# --------------------
ENTITY_INFO = {
    "PATIENT": "Nomi di pazienti",
    "PER": "Persone (nomi e cognomi)",
    "LOC": "Luoghi (posizioni, vie)",
    "ORG": "Organizzazioni",
    "FAC": "Strutture e impianti",
    "GPE": "Entità geopolitiche (paesi, regioni, città)",
    "NORP": "Nazionalità, gruppi religiosi o politici",
    "AGE": "Età della persona",
    "DATE": "Date e riferimenti temporali",
    "EVENT": "Eventi",
    "WORKS_OF_ART": "Titoli di opere",
    "PRODUCT": "Prodotti",
    "CODE": "Codici (fiscali, postali, ecc.)",
    "MAIL": "Indirizzi e-mail",
    "PHONE": "Numeri di telefono",
    "PROV": "Province italiane (sigle)",
    "URL": "Siti web / URL",
}


class AnonymizerApp:

    EXTRA_PER_MATCHING_OPTIONS = {
        "Nessuna": 0,
        "Parziale": 1,
        "Totale": 2,
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Anonimizzatore Digit-Care")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)

        self.selected_files = []
        self.output_dir = ""
        self.use_name_dictionary_label = tk.StringVar(value="Nessuna")
        self.outputs_in_single_file = tk.BooleanVar(value=DEFAULT_OUTPUTS_IN_SINGLE_FILE)
        self.use_multiprocessing = tk.BooleanVar(value=MULTI_PROCESSING)
        self.n_cores = tk.IntVar(value=P_CORES)
        self.cores_label = None
        self.cores_spinbox = None

        # --- MAIN PANED WINDOW (RESIZABLE SECTIONS) ---
        main_pane = ttk.PanedWindow(root, orient="horizontal")
        main_pane.pack(fill="both", expand=True)

        # LEFT PANEL (file selection + entities)
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=3)  # give more weight to left (entity table)

        # RIGHT PANEL (log)
        right_frame = ttk.Frame(main_pane, padding=(0, 10, 0, 0))
        main_pane.add(right_frame, weight=1)

        # --- BANNER (full-width, no title) ---
        banner_frame = ttk.Frame(left_frame, padding=(10, 10, 10, 10))
        banner_frame.pack(fill="x", pady=5)

        banner_path = Path(__file__).parent / "banner.png"

        if banner_path.exists():
            try:
                # Load original image
                self.banner_original = Image.open(banner_path)
                self.banner_photo = ImageTk.PhotoImage(self.banner_original)

                # Create label and pack it (this step was missing)
                self.banner_label = ttk.Label(banner_frame, image=self.banner_photo)
                self.banner_label.pack(fill="x", expand=True)

                # Resize dynamically
                banner_frame.bind("<Configure>", self._resize_banner)

            except Exception:
                # Fallback
                try:
                    self.banner_img = tk.PhotoImage(file=str(banner_path))
                    self.banner_label = tk.Label(banner_frame, image=self.banner_img)
                    self.banner_label.pack(fill="x")
                except Exception:
                    tk.Label(banner_frame, text="[banner.png non caricato]", font=("Arial", 12)).pack(fill="x")
        else:
            tk.Label(banner_frame, text="[banner.png non trovato]", font=("Arial", 12)).pack(fill="x")

        # --- FILE SELECTION FRAME ---
        file_frame = ttk.LabelFrame(left_frame, text="1. Seleziona file o cartella")
        file_frame.pack(fill="x", padx=10, pady=6)

        btn_frame = ttk.Frame(file_frame)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="Seleziona File", command=self.select_files).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Seleziona Cartella", command=self.select_folder).pack(side="left", padx=5)
        ttk.Label(btn_frame).pack(side="left", expand=True)  # spacer
        info_btn = ttk.Button(
            btn_frame,
            text="ⓘ",
            width=3,
            command=self.show_input_format_info
        )
        info_btn.pack(side="right", padx=5)

        self.file_listbox = tk.Listbox(file_frame, height=4)
        self.file_listbox.pack(fill="x", padx=10, pady=5)

        # --- ENTITY TABLE FRAME (SCROLLABLE) ---
        entity_frame = ttk.LabelFrame(left_frame, text="2. Seleziona entità da anonimizzare")
        entity_frame.pack(fill="both", expand=True, padx=10, pady=6)
        entity_frame.configure(height=200)

        advanced_frame = ttk.Frame(left_frame)
        advanced_frame.pack(fill="x", padx=10, pady=(0, 5))

        ttk.Label(advanced_frame).pack(side="left", expand=True)

        # --- OPTIONS FRAME (button) ---
        ttk.Button(
            advanced_frame,
            text="⚙ Impostazioni avanzate",
            command=self.show_advanced_settings
        ).pack(side="right")

        canvas = tk.Canvas(entity_frame, height=200)
        scroll = ttk.Scrollbar(entity_frame, orient="vertical", command=canvas.yview)
        self.entity_inner = ttk.Frame(canvas)

        # --- Enable mouse wheel scrolling ---
        def _on_mousewheel(event):
            # Windows / Linux
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_mac(event):
            # macOS uses different delta
            canvas.yview_scroll(int(-1 * event.delta), "units")

        # Bind depending on platform
        if sys.platform == "darwin":
            canvas.bind_all("<MouseWheel>", _on_mousewheel_mac)
        else:
            canvas.bind_all("<MouseWheel>", _on_mousewheel)


        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        canvas.create_window((0, 0), window=self.entity_inner, anchor="nw")
        self.entity_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # headings (no examples column)
        ttk.Label(self.entity_inner, text="", width=3).grid(row=0, column=0, padx=4, pady=4)  # checkbox column
        ttk.Label(self.entity_inner, text="Entità", font=(None, 10, "bold")).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(self.entity_inner, text="Descrizione", font=(None, 10, "bold")).grid(row=0, column=2, sticky="w", padx=4)

        # Build table of labels + descriptions
        self.entity_vars = {}

        for r, label in enumerate(ANONYMIZATION_LABELS, start=1):
            var = tk.BooleanVar(value=(label in DEFAULT_ENTITIES))
            self.entity_vars[label] = var

            ttk.Checkbutton(self.entity_inner, variable=var).grid(row=r, column=0, sticky="nw", padx=5, pady=6)
            ttk.Label(self.entity_inner, text=label).grid(row=r, column=1, sticky="w", padx=8, pady=6)
            desc = ENTITY_INFO.get(label, "")
            ttk.Label(self.entity_inner, text=desc, wraplength=740, justify="left").grid(row=r, column=2, sticky="w", padx=8, pady=6)

        # --- OUTPUT DIRECTORY FRAME ---
        output_frame = ttk.LabelFrame(left_frame, text="3. Cartella di destinazione")
        output_frame.pack(fill="x", padx=10, pady=6)

        ttk.Button(output_frame, text="Seleziona cartella", command=self.select_output_folder).pack(side="left", padx=5, pady=6)
        self.output_label = ttk.Label(output_frame, text="Nessuna cartella selezionata", foreground="gray")
        self.output_label.pack(side="left", padx=10)

        # --- ACTION BUTTONS ---
        action_frame = ttk.Frame(left_frame)
        action_frame.pack(fill="x", padx=10, pady=8)

        ttk.Button(action_frame, text="Anonimizza Documenti", command=self.anonymize_documents).pack(side="left", padx=10)
        ttk.Button(action_frame, text="Esci", command=root.quit).pack(side="right", padx=10)

        # --- LOG BOX (Right panel) ---
        log_label = ttk.Label(right_frame, text="Log", font=("Arial", 12, "bold"))
        log_label.pack(anchor="w", padx=5, pady=5)

        self.status_box = tk.Text(right_frame, height=20, bg="#f7f7f7")
        self.status_box.pack(fill="both", expand=True, padx=10, pady=10)


    # --------------------------------------------------------------------
    # Utility methods
    # --------------------------------------------------------------------
    def log(self, message):
        self.status_box.insert("end", message + "\n")
        self.status_box.see("end")

    def _resize_banner(self, event):
        """Resize banner image proportionally when frame size changes."""
        if not hasattr(self, "banner_original"):
            return

        new_w = event.width -20
        orig_w, orig_h = self.banner_original.size

        # keep aspect ratio
        ratio = new_w / orig_w
        new_h = int(orig_h * ratio)

        resized = self.banner_original.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.banner_photo = ImageTk.PhotoImage(resized)
        self.banner_label.config(image=self.banner_photo)

    def select_files(self):
        files = filedialog.askopenfilenames(title="Seleziona File", filetypes=[("Documenti", "*.pdf *.docx *.json *.txt")])
        if files:
            self.selected_files = list(files)
            self.file_listbox.delete(0, "end")
            for f in self.selected_files:
                self.file_listbox.insert("end", f)
            self.log(f"Selezionati {len(files)} file.")

    def select_folder(self):
        folder = filedialog.askdirectory(title="Seleziona Cartella")
        if folder:
            self.selected_files = [os.path.join(folder, f) for f in os.listdir(folder)
                                   if f.lower().endswith((".pdf", ".docx", ".json", ".txt"))]
            self.file_listbox.delete(0, "end")
            for f in self.selected_files:
                self.file_listbox.insert("end", f)
            self.log(f"Caricati tutti i documenti da: {folder}")

    def select_output_folder(self):
        folder = filedialog.askdirectory(title="Seleziona cartella")
        if folder:
            self.output_dir = folder
            self.output_label.config(text=folder, foreground="black")
            self.log(f"Cartella di output impostata: {folder}")

    def show_input_format_info(self):
        info_win = tk.Toplevel(self.root)
        info_win.title("Formato JSON di input")
        info_win.geometry("500x720")
        info_win.transient(self.root)
        info_win.grab_set()

        ttk.Label(
            info_win,
            text="Struttura Attesa dei File JSON",
            font=("Arial", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(5, 0))

        # Legend (smaller, muted)
        ttk.Label(
            info_win,
            text=LEGEND,
            font=("Arial", 9),
            foreground="gray",
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 0))

        frame = ttk.Frame(info_win)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        text = tk.Text(frame, wrap="none")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        json_example = JSON_EXAMPLE
        text.insert("1.0", json_example.strip())
        text.configure(state="disabled")

    def _on_multiprocessing_toggle(self, *_):
        """Enable/disable cores spinbox based on checkbox state."""
        if self.use_multiprocessing.get():
            self.cores_spinbox.config(state="normal")
            self.cores_label.config(foreground="black")
        else:
            self.cores_spinbox.config(state="disabled")
            self.cores_label.config(foreground="gray")

    def show_advanced_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Impostazioni avanzate")
        win.geometry("650x400")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(
            win,
            text="Impostazioni avanzate",
            font=("Arial", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 8))

        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=20)

        # --- Existing options ---
        ttk.Label(
            frame,
            text="Anonimizzazione aggiuntiva per nomi e cognomi tramite dizionari:",
            font=("Arial", 9),
            foreground="black"
        ).pack(anchor="w", pady=(8, 0))

        ttk.Combobox(
            frame,
            textvariable=self.use_name_dictionary_label,
            values=sorted(list(self.EXTRA_PER_MATCHING_OPTIONS.keys())),
            state="readonly",
            width=15
        ).pack(anchor="w", padx=5)

        ttk.Label(
            frame,
            text=(
                "Legenda:\n"
                "\t• Nessuna: non applica regole aggiuntive per nomi e cognomi.\n"
                "\t• Parziale: anonimizza solo nomi e cognomi che non coincidono con parole del dizionario italiano.\n"
                "\t• Totale: anonimizza tutti i nomi e cognomi conosciuti."
            ),
            font=("Arial", 9),
            foreground="gray"
        ).pack(anchor="w", pady=(8, 0))

        ttk.Checkbutton(
            frame,
            text="Salva più testi dei JSON in file separati",
            variable=self.outputs_in_single_file
        ).pack(anchor="w", pady=4)

        ttk.Separator(frame).pack(fill="x", pady=10)

        # --- New multiprocessing options ---
        ttk.Checkbutton(
            frame,
            text="Abilita multiprocessing",
            variable=self.use_multiprocessing
        ).pack(anchor="w", pady=4)

        cores_frame = ttk.Frame(frame)
        cores_frame.pack(anchor="w", pady=4)

        self.cores_label = ttk.Label(
            cores_frame,
            text="Numero di core da utilizzare:"
        )
        self.cores_label.pack(side="left")

        self.cores_spinbox = ttk.Spinbox(
            cores_frame,
            from_=1,
            to=os.cpu_count() or 16,
            width=5,
            textvariable=self.n_cores,
            state="disabled"
        )
        self.cores_spinbox.pack(side="left", padx=5)

        self.use_multiprocessing.trace_add("write",self._on_multiprocessing_toggle)

        ttk.Label(
            frame,
            text="Nota: il multiprocessing è utile solo con un grande numero di testi. \nPer ogni core coinvolto, "
                 "è raccomandabile disporre di almeno 1.5GB di memoria RAM disponibile. \nPer massimizzare "
                 "le prestazioni, mantenere aperta la finestra dell'applicazione durante l'anonimizzazione.",
            font=("Arial", 9),
            foreground="gray"
        ).pack(anchor="w", pady=(8, 0))

        # --- Close button ---
        ttk.Button(win, text="Chiudi", command=win.destroy).pack(pady=10)

    def show_metrics_table(self, metrics: dict):
        win = tk.Toplevel(self.root)
        win.title("Metriche di valutazione")
        win.geometry("650x400")
        win.transient(self.root)
        win.grab_set()

        title_frame = ttk.Frame(win)
        title_frame.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(
            title_frame,
            text="Metriche per Etichetta",
            font=("Arial", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        ttk.Label(title_frame).pack(side="left", expand=True)  # spacer

        info_btn = ttk.Button(
            title_frame,
            text="ⓘ",
            width=3,
            command=self.show_metrics_info
        )
        info_btn.pack(side="right")

        # ---- Table frame ----
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        columns = ("precision", "recall", "coverage", "f1")

        tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings"
        )

        # Headings
        tree.heading("precision", text="Precision")
        tree.heading("recall", text="Recall")
        tree.heading("coverage", text="Coverage")
        tree.heading("f1", text="F1")

        # Column config
        tree.column("precision", width=100, anchor="center")
        tree.column("recall", width=100, anchor="center")
        tree.column("coverage", width=100, anchor="center")
        tree.column("f1", width=100, anchor="center")

        # Row label column
        tree["displaycolumns"] = columns
        tree.pack(side="left", fill="both", expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # ---- Populate rows ----
        def fmt(value):
            return f"{value:.3f}" if isinstance(value, (int, float)) else "—"

        for label, values in metrics.items():
            row = [
                fmt(values.get("precision")),
                fmt(values.get("recall")),
                fmt(values.get("coverage")),
                fmt(values.get("f1")),
            ]

            tree.insert("", "end", text=label, values=row, iid=label)

        # Add first column (labels)
        tree["show"] = "tree headings"
        tree.heading("#0", text="Etichetta")
        tree.column("#0", width=120, anchor="w")

    def show_metrics_info(self):
        info_win = tk.Toplevel(self.root)
        info_win.title("Significato delle metriche")
        info_win.geometry("600x600")
        info_win.transient(self.root)
        info_win.grab_set()

        ttk.Label(
            info_win,
            text="Descrizione delle metriche di valutazione",
            font=("Arial", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        text = tk.Text(info_win, wrap="word", height=18)
        text.pack(fill="both", expand=True, padx=10, pady=10)

        explanation = METRICS_EXPLAINATION

        text.insert("1.0", explanation.strip())
        text.configure(state="disabled", font=("Arial", 10))

    def anonymize_documents(self):
        self.log("Anonimizzazione in corso...")
        threading.Thread(target=self._anonymize_worker).start()


    # Main anonymization loop
    def _anonymize_worker(self):
        if not self.selected_files:
            self.root.after(0, lambda: messagebox.showwarning("Attenzione", "Seleziona almeno un documento."))
            return
        if not self.output_dir:
            self.root.after(0, lambda: messagebox.showwarning("Attenzione", "Seleziona una cartella di output."))
            return

        selected_entities = [ent for ent, var in self.entity_vars.items() if var.get()]
        if not selected_entities:
            self.root.after(0,
                            lambda: messagebox.showwarning("Attenzione", "Seleziona almeno una categoria di entità."))
            return

        all_texts = []
        all_metadata = []
        all_per_data = []
        for file_path in self.selected_files:
            try:
                texts, metadata, per_data = read_file(file_path)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Errore", f"Impossibile leggere {file_path}: {e}"))
                continue

            if all(not text.strip() for text in texts):
                self.root.after(0, lambda f=file_path: self.log(f"Saltato (vuoto): {f}"))
                continue

            all_texts.extend(texts)
            all_metadata.extend(metadata)
            all_per_data.extend([copy.deepcopy(per_data) for _ in texts])

        start_time = time.time()
        anonymized, metrics = anonymize_texts(all_texts, entities=selected_entities,
                                              per_matching=self.EXTRA_PER_MATCHING_OPTIONS[self.use_name_dictionary_label.get()],
                                              personal_data=all_per_data, meta_data=all_metadata,
                                              multi_processing=self.use_multiprocessing.get(),
                                              p_cores=self.n_cores.get())
        end_time = time.time()

        out_path = save_many_texts(
            anonymized,
            output_dir=self.output_dir,
            original_filename=self.selected_files[0] if len(self.selected_files) >= 1 else None,
            single_file=self.outputs_in_single_file.get(),
            metadata=all_metadata,
            personal_data=all_per_data
        )

        self.root.after(0, lambda p=out_path: self.log(f"File anonimizzato in {end_time - start_time:.2f} secondi. Salvato in: {p}"))

        if metrics:
            save_metrics(metrics, output_dir=os.path.dirname(out_path), original_filename=os.path.basename(out_path))
            self.root.after(0, lambda: self.log("Metriche di valutazione salvate."))
            self.show_metrics_table(metrics)

        self.root.after(0, lambda: messagebox.showinfo("Fatto", "Anonimizzazione completata con successo!"))
        self.root.after(0, lambda: self.log("Tutti i file sono stati processati con successo."))


# Entry point
def main():
    root = tk.Tk()
    app = AnonymizerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
