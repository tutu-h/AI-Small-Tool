from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from boss_tool.bailian import BailianClient
from boss_tool.capture import BossWindowCapture, ImageFileCapture
from boss_tool.config import AppConfig, ConfigStore, sanitize_config
from boss_tool.exporter import export_snapshot
from boss_tool.history import HistoryStore
from boss_tool.monitor import MonitorController
from boss_tool.ocr import OcrService
from boss_tool.pipeline import BossInsightPipeline


class BossToolApp:
    def __init__(self, root: tk.Tk, config_store: ConfigStore) -> None:
        self.root = root
        self.config_store = config_store
        self.config = config_store.load()
        self.snapshot = None
        self.history_store = HistoryStore(config_store.path.with_name("history.json"))
        self.scan_history: list[object] = self.history_store.load()
        self.imported_image_path: str | None = None
        self.conversation_row_map: dict[str, object] = {}

        self.status_var = tk.StringVar(value="就绪")
        self.window_var = tk.StringVar(value="未连接")
        self.unread_var = tk.StringVar(value="0")
        self.conversation_var = tk.StringVar(value="0")
        self.message_var = tk.StringVar(value="0")
        self.fallback_var = tk.StringVar(value="未触发")
        self.scan_mode_var = tk.StringVar(value="未知")
        self.vision_recommendation_var = tk.StringVar(value="否")
        self.scan_diagnostics_var = tk.StringVar(value="等待扫描")

        self.monitor = MonitorController(self._scan_async)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="boss-scan")
        self.warmup_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="boss-warm")
        self.scan_future: Future | None = None
        self.ocr_service = OcrService()
        self.analyzer: BailianClient | None = None
        self._service_signature: tuple[str, str, str, str] | None = None
        self._root_hidden_for_scan = False

        self.base_url_var = tk.StringVar(value=self.config.base_url)
        self.api_key_var = tk.StringVar(value=self.config.api_key)
        self.text_model_var = tk.StringVar(value=self.config.text_model)
        self.vision_model_var = tk.StringVar(value=self.config.vision_model)
        self.interval_var = tk.IntVar(value=self.config.monitor_interval_seconds)
        self.keyword_var = tk.StringVar(value=self.config.boss_window_keyword)
        self.prefer_vision_for_web_var = tk.BooleanVar(
            value=self.config.prefer_vision_for_web
        )

        self._build_ui()
        self._refresh_scan_history()
        self.warmup_executor.submit(self.ocr_service.warm_up)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.root.title("Boss Insight Assistant")
        self.root.geometry("1500x920")
        self.root.configure(bg="#F3F6FB")

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("App.TFrame", background="#F3F6FB")
        style.configure("Card.TLabelframe", background="#FFFFFF", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background="#FFFFFF", foreground="#1F2A37", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("MetricValue.TLabel", background="#FFFFFF", foreground="#111827", font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("MetricTitle.TLabel", background="#FFFFFF", foreground="#6B7280", font=("Microsoft YaHei UI", 10))
        style.configure("SectionTitle.TLabel", background="#FFFFFF", foreground="#0F172A", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("Soft.TLabel", background="#FFFFFF", foreground="#6B7280", font=("Microsoft YaHei UI", 9))
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"))

        main = ttk.Frame(self.root, style="App.TFrame", padding=14)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=3)
        main.columnconfigure(2, weight=2)
        main.rowconfigure(0, weight=1)

        self._build_control_panel(main)
        self._build_workspace(main)
        self._build_ai_panel(main)

    def _build_control_panel(self, parent: ttk.Frame) -> None:
        control = ttk.LabelFrame(parent, text="控制台", padding=12, style="Card.TLabelframe")
        control.grid(row=0, column=0, sticky="nsw", padx=(0, 12))

        ttk.Label(control, text="Base URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(control, textvariable=self.base_url_var, width=34).grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(control, text="API Key").grid(row=2, column=0, sticky="w")
        ttk.Entry(control, textvariable=self.api_key_var, width=34, show="*").grid(row=3, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(control, text="文本模型").grid(row=4, column=0, sticky="w")
        ttk.Entry(control, textvariable=self.text_model_var, width=34).grid(row=5, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(control, text="视觉模型").grid(row=6, column=0, sticky="w")
        ttk.Entry(control, textvariable=self.vision_model_var, width=34).grid(row=7, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(control, text="Boss窗口关键词").grid(row=8, column=0, sticky="w")
        ttk.Entry(control, textvariable=self.keyword_var, width=34).grid(row=9, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(control, text="监控间隔(秒)").grid(row=10, column=0, sticky="w")
        ttk.Spinbox(control, from_=2, to=60, textvariable=self.interval_var, width=8).grid(row=11, column=0, sticky="w", pady=(0, 12))
        ttk.Checkbutton(
            control,
            text="网页端优先走视觉识别",
            variable=self.prefer_vision_for_web_var,
        ).grid(row=12, column=0, sticky="w", pady=(0, 12))

        ttk.Button(control, text="保存配置", command=self.save_config, style="Primary.TButton").grid(row=13, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(control, text="立即扫描窗口", command=self.scan_now).grid(row=14, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(control, text="导入截图识别", command=self.import_image).grid(row=15, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(control, text="开始监控", command=self.start_monitoring).grid(row=16, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(control, text="停止监控", command=self.stop_monitoring).grid(row=17, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(control, text="导出本次结果", command=self.export_current_snapshot).grid(row=18, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(control, text="复制AI建议", command=self.copy_analysis).grid(row=19, column=0, sticky="ew", pady=(0, 10))

        info = ttk.Frame(control, style="App.TFrame")
        info.grid(row=20, column=0, sticky="ew")
        ttk.Label(info, text="状态", style="Soft.TLabel").pack(anchor="w")
        ttk.Label(info, textvariable=self.status_var, wraplength=240, background="#FFFFFF", foreground="#111827").pack(anchor="w", pady=(0, 8))
        ttk.Label(info, text="当前来源", style="Soft.TLabel").pack(anchor="w")
        ttk.Label(info, textvariable=self.window_var, wraplength=240, background="#FFFFFF", foreground="#111827").pack(anchor="w")
        ttk.Label(info, text="识别诊断", style="Soft.TLabel").pack(anchor="w", pady=(8, 0))
        ttk.Label(info, textvariable=self.scan_diagnostics_var, wraplength=240, background="#FFFFFF", foreground="#111827").pack(anchor="w")

    def _build_workspace(self, parent: ttk.Frame) -> None:
        workspace = ttk.Frame(parent, style="App.TFrame")
        workspace.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        workspace.rowconfigure(1, weight=1)
        workspace.rowconfigure(2, weight=2)
        workspace.columnconfigure(0, weight=1)

        overview = ttk.LabelFrame(workspace, text="扫描概览", padding=12, style="Card.TLabelframe")
        overview.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for idx in range(4):
            overview.columnconfigure(idx, weight=1)
        self._build_metric(overview, 0, "未读总数", self.unread_var)
        self._build_metric(overview, 1, "候选人会话", self.conversation_var)
        self._build_metric(overview, 2, "当前消息数", self.message_var)
        self._build_metric(overview, 3, "视觉兜底", self.fallback_var)
        self._build_metric(overview, 4, "识别模式", self.scan_mode_var)
        self._build_metric(overview, 5, "建议走视觉", self.vision_recommendation_var)

        conversation_card = ttk.LabelFrame(workspace, text="候选人列表与未读会话", padding=10, style="Card.TLabelframe")
        conversation_card.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        conversation_card.rowconfigure(0, weight=1)
        conversation_card.columnconfigure(0, weight=1)

        columns = ("name", "job", "time", "unread", "message")
        self.conversation_tree = ttk.Treeview(
            conversation_card,
            columns=columns,
            show="headings",
            height=10,
        )
        headings = {
            "name": "候选人",
            "job": "岗位/标签",
            "time": "时间",
            "unread": "未读",
            "message": "最近消息",
        }
        widths = {
            "name": 110,
            "job": 210,
            "time": 70,
            "unread": 60,
            "message": 320,
        }
        for key in columns:
            self.conversation_tree.heading(key, text=headings[key])
            self.conversation_tree.column(key, width=widths[key], anchor="w")
        self.conversation_tree.grid(row=0, column=0, sticky="nsew")
        self.conversation_tree.bind("<<TreeviewSelect>>", self._on_conversation_selected)
        conversation_scroll = ttk.Scrollbar(conversation_card, orient="vertical", command=self.conversation_tree.yview)
        self.conversation_tree.configure(yscrollcommand=conversation_scroll.set)
        conversation_scroll.grid(row=0, column=1, sticky="ns")

        details = ttk.Frame(workspace, style="App.TFrame")
        details.grid(row=2, column=0, sticky="nsew")
        details.columnconfigure(0, weight=2)
        details.columnconfigure(1, weight=3)
        details.rowconfigure(0, weight=1)

        candidate_card = ttk.LabelFrame(details, text="当前候选人卡片", padding=12, style="Card.TLabelframe")
        candidate_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        candidate_card.rowconfigure(1, weight=1)
        candidate_card.columnconfigure(0, weight=1)
        self.candidate_name_label = ttk.Label(candidate_card, text="未识别候选人", style="SectionTitle.TLabel")
        self.candidate_name_label.grid(row=0, column=0, sticky="w")
        self.candidate_text = tk.Text(candidate_card, wrap="word", height=14, bg="#F8FAFC", relief="flat", font=("Microsoft YaHei UI", 10))
        self.candidate_text.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        chat_card = ttk.LabelFrame(details, text="当前未读消息与聊天内容", padding=12, style="Card.TLabelframe")
        chat_card.grid(row=0, column=1, sticky="nsew")
        chat_card.rowconfigure(0, weight=1)
        chat_card.columnconfigure(0, weight=1)
        self.chat_text = tk.Text(chat_card, wrap="word", bg="#F8FAFC", relief="flat", font=("Microsoft YaHei UI", 10))
        self.chat_text.grid(row=0, column=0, sticky="nsew")

    def _build_ai_panel(self, parent: ttk.Frame) -> None:
        ai_card = ttk.LabelFrame(parent, text="招聘 AI 建议工作台", padding=12, style="Card.TLabelframe")
        ai_card.grid(row=0, column=2, sticky="nsew")
        ai_card.columnconfigure(0, weight=1)
        ai_card.rowconfigure(1, weight=1)
        ai_card.rowconfigure(5, weight=1)
        ai_card.rowconfigure(7, weight=1)
        ai_card.rowconfigure(9, weight=1)

        ttk.Label(ai_card, text="最近扫描历史", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.history_listbox = tk.Listbox(ai_card, height=5, bg="#F8FAFC", relief="flat", font=("Microsoft YaHei UI", 9))
        self.history_listbox.grid(row=1, column=0, sticky="nsew", pady=(6, 12))
        self.history_listbox.bind("<<ListboxSelect>>", self._on_history_selected)

        ttk.Label(ai_card, text="全部未读摘要", style="SectionTitle.TLabel").grid(row=2, column=0, sticky="w")
        self.unread_summary_text = tk.Text(ai_card, wrap="word", height=5, bg="#F8FAFC", relief="flat", font=("Microsoft YaHei UI", 10))
        self.unread_summary_text.grid(row=3, column=0, sticky="ew", pady=(6, 12))

        ttk.Label(ai_card, text="当前聊天判断", style="SectionTitle.TLabel").grid(row=4, column=0, sticky="w")
        self.current_summary_text = tk.Text(ai_card, wrap="word", height=6, bg="#F8FAFC", relief="flat", font=("Microsoft YaHei UI", 10))
        self.current_summary_text.grid(row=5, column=0, sticky="nsew", pady=(6, 12))

        ttk.Label(ai_card, text="优先级与跟进动作", style="SectionTitle.TLabel").grid(row=6, column=0, sticky="w")
        self.priority_listbox = tk.Listbox(ai_card, height=8, bg="#F8FAFC", relief="flat", font=("Microsoft YaHei UI", 10))
        self.priority_listbox.grid(row=7, column=0, sticky="nsew", pady=(6, 12))

        ttk.Label(ai_card, text="快捷回复建议", style="SectionTitle.TLabel").grid(row=8, column=0, sticky="w")
        self.reply_text = tk.Text(ai_card, wrap="word", bg="#F8FAFC", relief="flat", font=("Microsoft YaHei UI", 10))
        self.reply_text.grid(row=9, column=0, sticky="nsew", pady=(6, 0))

    def _build_metric(self, parent: ttk.LabelFrame, column: int, title: str, variable: tk.StringVar) -> None:
        card = ttk.Frame(parent, style="App.TFrame")
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        ttk.Label(card, text=title, style="MetricTitle.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=variable, style="MetricValue.TLabel").pack(anchor="w", pady=(4, 0))

    def save_config(self) -> None:
        self.config = build_config_from_values(
            base_url=read_var_value(self.base_url_var),
            api_key=read_var_value(self.api_key_var),
            text_model=read_var_value(self.text_model_var),
            vision_model=read_var_value(self.vision_model_var),
            interval_value=read_var_value(self.interval_var),
            boss_window_keyword=read_var_value(self.keyword_var),
            prefer_vision_for_web=read_var_value(self.prefer_vision_for_web_var, False),
        )
        self.config_store.save(self.config)
        self._refresh_services()
        self.status_var.set("配置已保存")

    def scan_now(self) -> None:
        self.save_config()
        self.imported_image_path = None
        self._scan_async()

    def import_image(self) -> None:
        self.save_config()
        image_path = filedialog.askopenfilename(
            title="选择 Boss 直聘截图",
            filetypes=[
                ("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.webp"),
                ("所有文件", "*.*"),
            ],
        )
        if not image_path:
            return
        self.imported_image_path = image_path
        self._scan_async()

    def _scan_async(self) -> None:
        if self.scan_future and not self.scan_future.done():
            self.status_var.set("上一次扫描还在进行，请稍候")
            return
        self.status_var.set("扫描中...")
        pipeline = self._build_pipeline()
        self._prepare_window_for_scan()
        self.scan_future = self.executor.submit(pipeline.run_scan)
        self.scan_future.add_done_callback(
            lambda future: self.root.after(0, self._handle_scan_result, future)
        )

    def _handle_scan_result(self, future: Future) -> None:
        self._restore_window_after_scan()
        try:
            snapshot = future.result()
        except Exception as exc:
            self.status_var.set(f"扫描失败: {exc}")
            messagebox.showerror("扫描失败", str(exc))
            return
        self.snapshot = snapshot
        self._record_scan_history(snapshot)
        self._render_snapshot(snapshot)
        self.status_var.set("扫描完成")

    def _prepare_window_for_scan(self) -> None:
        if self.imported_image_path:
            return
        try:
            self.root.withdraw()
            self.root.update_idletasks()
        except Exception:
            return
        self._root_hidden_for_scan = True

    def _restore_window_after_scan(self) -> None:
        if not getattr(self, "_root_hidden_for_scan", False):
            return
        try:
            self.root.deiconify()
        finally:
            self._root_hidden_for_scan = False

    def _refresh_services(self) -> None:
        signature = (
            self.config.base_url,
            self.config.api_key,
            self.config.text_model,
            self.config.vision_model,
        )
        if not self.config.api_key:
            self.analyzer = None
            self._service_signature = None
            return
        if signature != self._service_signature:
            self.analyzer = BailianClient(self.config)
            self._service_signature = signature

    def _build_pipeline(self) -> BossInsightPipeline:
        self._refresh_services()
        if self.imported_image_path:
            capture = ImageFileCapture(self.imported_image_path)
        else:
            capture = BossWindowCapture(self.config)
        return BossInsightPipeline(
            capture_service=capture,
            ocr_service=self.ocr_service,
            vision_service=self.analyzer,
            analyzer=self.analyzer,
        )

    def _render_snapshot(self, snapshot) -> None:
        source_label = snapshot.window.title if snapshot.window.found else "未找到 Boss 窗口"
        if snapshot.diagnostics.get("capture_mode") == "imported_image":
            source_label = f"导入截图: {snapshot.window.title}"
        self.window_var.set(source_label)

        total_unread = sum(item.unread_count for item in snapshot.conversation_list)
        self.unread_var.set(str(total_unread))
        self.conversation_var.set(str(len(snapshot.conversation_list)))
        self.message_var.set(str(len(snapshot.current_messages)))
        self.fallback_var.set("已触发" if snapshot.diagnostics.get("fallback_used") else "未触发")
        self.scan_mode_var.set(build_scan_mode_label(snapshot.diagnostics, snapshot.window.title))
        self.vision_recommendation_var.set(
            "是" if snapshot.diagnostics.get("vision_recommended") else "否"
        )
        self.scan_diagnostics_var.set(build_scan_diagnostics_content(snapshot.diagnostics))

        for row_id in self.conversation_tree.get_children():
            self.conversation_tree.delete(row_id)
        self.conversation_row_map.clear()
        first_row_id = None
        for index, item in enumerate(snapshot.conversation_list):
            row_id = self.conversation_tree.insert(
                "",
                tk.END,
                values=(
                    item.name,
                    item.job_title,
                    item.time_label,
                    item.unread_count,
                    item.last_message,
                ),
            )
            self.conversation_row_map[row_id] = item
            if first_row_id is None:
                first_row_id = row_id
            if index == 0:
                item.selected = True
            else:
                item.selected = False
        if first_row_id is not None:
            self.conversation_tree.selection_set(first_row_id)

        self._refresh_candidate_card()

        self._fill_text(self.chat_text, build_chat_panel_content(snapshot))

        sections = format_analysis_sections(snapshot.analysis)
        self._fill_text(self.unread_summary_text, sections["unread_summary"])
        self._fill_text(self.current_summary_text, sections["current_chat_summary"])

        self.priority_listbox.delete(0, tk.END)
        for item in sections["priorities"]:
            self.priority_listbox.insert(tk.END, item)

        self._fill_text(self.reply_text, "\n\n".join(sections["reply_suggestions"]))
        self._refresh_scan_history()

    def start_monitoring(self) -> None:
        self.save_config()
        self.imported_image_path = None
        self.monitor.start(self.config.monitor_interval_seconds)
        self.status_var.set("监控中")

    def stop_monitoring(self) -> None:
        self.monitor.stop()
        self.status_var.set("监控已停止")

    def copy_analysis(self) -> None:
        content = self.reply_text.get("1.0", tk.END).strip()
        if not content:
            self.status_var.set("没有可复制的 AI 建议")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.root.update_idletasks()
        self.status_var.set("AI 建议已复制到剪贴板")

    def export_current_snapshot(self) -> None:
        if self.snapshot is None:
            self.status_var.set("还没有可导出的扫描结果")
            return
        export_path = filedialog.asksaveasfilename(
            title="导出 Boss 识别结果",
            defaultextension=".md",
            filetypes=[
                ("Markdown", "*.md"),
                ("JSON", "*.json"),
            ],
        )
        if not export_path:
            return
        try:
            export_snapshot(self.snapshot, export_path)
        except Exception as exc:
            self.status_var.set(f"导出失败: {exc}")
            messagebox.showerror("导出失败", str(exc))
            return
        self.status_var.set(f"已导出: {export_path}")

    def _fill_text(self, widget: tk.Text, content: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)

    def _record_scan_history(self, snapshot) -> None:
        if not should_record_scan_history(snapshot):
            self.status_var.set("本次扫描无有效识别内容，未写入历史")
            return
        self.scan_history.append(snapshot)
        self.scan_history = self.scan_history[-20:]
        try:
            self.history_store.save(self.scan_history)
        except Exception as exc:
            self.status_var.set(f"历史保存失败: {exc}")

    def _refresh_scan_history(self) -> None:
        self.history_listbox.delete(0, tk.END)
        for entry in build_history_entries(self.scan_history):
            self.history_listbox.insert(tk.END, entry)

    def _on_history_selected(self, _event=None) -> None:
        selected = self.history_listbox.curselection()
        if not selected:
            return
        self._replay_history_snapshot(selected[0])

    def _replay_history_snapshot(self, display_index: int) -> None:
        snapshot_index = history_index_to_snapshot_index(
            display_index,
            len(self.scan_history),
        )
        if snapshot_index is None:
            return
        snapshot = self.scan_history[snapshot_index]
        self.snapshot = snapshot
        self._render_snapshot(snapshot)
        self.status_var.set("已回放历史扫描")

    def _on_conversation_selected(self, _event=None) -> None:
        if self.snapshot is None:
            return
        selected_items = self.conversation_tree.selection()
        if not selected_items:
            return
        selected_row = selected_items[0]
        selected_conversation = self.conversation_row_map.get(selected_row)
        if selected_conversation is None:
            return
        for item in self.snapshot.conversation_list:
            item.selected = item is selected_conversation
        self._refresh_candidate_card()
        self._fill_text(self.chat_text, build_chat_panel_content(self.snapshot))

    def _refresh_candidate_card(self) -> None:
        if self.snapshot is None:
            self.candidate_name_label.config(text="未识别候选人")
            self._fill_text(self.candidate_text, "暂无候选人详情。")
            return
        candidate_title, candidate_details = build_candidate_card_content(self.snapshot)
        self.candidate_name_label.config(text=candidate_title)
        self._fill_text(self.candidate_text, candidate_details)

    def _on_close(self) -> None:
        self.monitor.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.warmup_executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def format_analysis_sections(analysis: dict | None) -> dict[str, list[str] | str]:
    analysis = analysis or {}
    return {
        "unread_summary": _normalize_text_block(
            analysis.get("unread_summary", "未配置 API Key，当前仅展示本地识别结果。")
        ),
        "current_chat_summary": _normalize_text_block(
            analysis.get("current_chat_summary", "暂无聊天判断。")
        ),
        "priorities": _normalize_list_block(
            analysis.get("priorities", ["暂无优先级建议。"])
        ),
        "reply_suggestions": _normalize_list_block(
            analysis.get("reply_suggestions", ["暂无回复建议。"])
        ),
    }


def build_candidate_card_content(snapshot) -> tuple[str, str]:
    current_conversation = _get_current_conversation(snapshot)
    profile = snapshot.current_candidate

    title = _pick_candidate_title(profile.name, current_conversation.name if current_conversation is not None else "")

    details: list[str] = []
    if current_conversation is not None:
        details.append(f"当前会话岗位：{current_conversation.job_title or '未识别'}")
        details.append(f"最近消息：{current_conversation.last_message or '暂无'}")
        details.append(f"会话时间：{current_conversation.time_label or '未知'}")
        details.append(f"未读消息：{current_conversation.unread_count}")

    if profile.summary_lines:
        details.append("")
        details.append("补充资料：")
        details.extend(profile.summary_lines)

    if not details:
        details.append("暂无候选人详情。")

    return title, "\n".join(details)


def build_chat_panel_content(snapshot) -> str:
    chat_lines: list[str] = []
    current_conversation = _get_current_conversation(snapshot)
    if snapshot.current_messages:
        chat_lines.append("精确聊天内容来自 Boss 当前打开的会话。")
        if current_conversation is not None:
            chat_lines.append(f"当前左侧选中：{current_conversation.name or '未识别候选人'}")
        chat_lines.append("")
        for item in snapshot.current_messages:
            prefix = item.speaker or "未知"
            time_label = f"[{item.time_label}] " if item.time_label else ""
            chat_lines.append(f"{time_label}{prefix}: {item.text}")

    if not chat_lines:
        if current_conversation is not None:
            chat_lines.append("未打开的左侧会话只能显示最近消息摘要。")
            chat_lines.append(f"候选人：{current_conversation.name or '未识别'}")
            chat_lines.append(f"岗位/标签：{current_conversation.job_title or '未识别'}")
            chat_lines.append(f"最近消息：{current_conversation.last_message or '暂无'}")
            chat_lines.append(f"未读消息数：{current_conversation.unread_count}")
        else:
            chat_lines.append("暂无聊天消息。")

    warnings = snapshot.diagnostics.get("warnings", [])
    if warnings:
        chat_lines.append("")
        chat_lines.append("诊断提示：")
        chat_lines.extend(f"- {item}" for item in warnings)
    return "\n".join(chat_lines)


def _normalize_text_block(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if str(item).strip())
    return str(value).strip()


def _normalize_list_block(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, dict):
                items.append(" | ".join(f"{k}: {v}" for k, v in item.items()))
            else:
                text = str(item).strip()
                if text:
                    items.append(text)
        return items
    return [str(value).strip()]


def _get_current_conversation(snapshot):
    for item in snapshot.conversation_list:
        if getattr(item, "selected", False):
            return item
    return snapshot.conversation_list[0] if snapshot.conversation_list else None


def _pick_candidate_title(profile_name: str, conversation_name: str) -> str:
    invalid_profile_names = {
        "",
        "会话",
        "消息",
        "全部",
        "在线简历",
        "附件简历",
        "工作经历",
    }
    if profile_name not in invalid_profile_names:
        return profile_name
    if conversation_name:
        return conversation_name
    return "未识别候选人"


def default_config_store() -> ConfigStore:
    app_dir = Path.home() / ".boss-insight-assistant"
    return ConfigStore(app_dir / "settings.json")


def build_config_from_values(
    *,
    base_url,
    api_key,
    text_model,
    vision_model,
    interval_value,
    boss_window_keyword,
    prefer_vision_for_web,
) -> AppConfig:
    return sanitize_config(
        AppConfig(
            base_url=base_url,
            api_key=api_key,
            text_model=text_model,
            vision_model=vision_model,
            monitor_interval_seconds=interval_value,
            boss_window_keyword=boss_window_keyword,
            prefer_vision_for_web=prefer_vision_for_web,
        )
    )


def read_var_value(variable, default=""):
    try:
        return variable.get()
    except Exception:
        return default


def build_scan_mode_label(diagnostics: dict, window_title: str) -> str:
    capture_mode = diagnostics.get("capture_mode")
    if capture_mode == "imported_image":
        return "导入截图"
    if diagnostics.get("is_web_boss"):
        return "网页端窗口"
    if capture_mode == "live_window":
        return "客户端窗口"
    return window_title or "未知"


def build_scan_diagnostics_content(diagnostics: dict) -> str:
    attempted_regions = _format_region_names(diagnostics.get("vision_regions_attempted", []))
    used_regions = _format_region_names(diagnostics.get("vision_regions_used", []))
    lines = [
        f"布局：{diagnostics.get('layout_mode', '未知')}",
        f"建议视觉兜底：{'是' if diagnostics.get('vision_recommended') else '否'}",
        f"兜底已生效：{'是' if diagnostics.get('fallback_used') else '否'}",
        f"已尝试区域：{attempted_regions or '无'}",
        f"生效区域：{used_regions or '无'}",
    ]
    warnings = diagnostics.get("warnings", [])
    if warnings:
        lines.append("提示：" + "；".join(str(item) for item in warnings))
    return "\n".join(lines)


def _format_region_names(region_names) -> str:
    labels = {
        "conversation_list": "左侧会话列表",
        "candidate_header": "候选人资料区",
        "chat_body": "当前聊天区",
    }
    return "、".join(labels.get(str(name), str(name)) for name in region_names)


def build_history_entries(snapshots: list[object]) -> list[str]:
    entries: list[str] = []
    for snapshot in reversed(snapshots):
        conversations = getattr(snapshot, "conversation_list", [])
        total_unread = sum(item.unread_count for item in conversations)
        latest = _pick_history_latest_conversation(conversations)
        time_label = latest.time_label if latest is not None and latest.time_label else _snapshot_time(snapshot)
        if latest is None:
            preview = "暂无会话"
        else:
            name = latest.name or "未识别"
            message = latest.last_message or "暂无最近消息"
            preview = f"{name}：{message}"
        entries.append(
            f"{time_label} | {total_unread}未读 | {len(conversations)}会话 | {preview}"
        )
    return entries


def history_index_to_snapshot_index(
    display_index: int, history_length: int
) -> int | None:
    snapshot_index = history_length - display_index - 1
    if snapshot_index < 0 or snapshot_index >= history_length:
        return None
    return snapshot_index


def should_record_scan_history(snapshot) -> bool:
    if not getattr(getattr(snapshot, "window", None), "found", False):
        return False
    return bool(
        getattr(snapshot, "conversation_list", [])
        or getattr(snapshot, "current_messages", [])
        or getattr(getattr(snapshot, "current_candidate", None), "name", "")
        or getattr(getattr(snapshot, "current_candidate", None), "summary_lines", [])
    )


def _pick_history_latest_conversation(conversations):
    if not conversations:
        return None
    for item in conversations:
        if getattr(item, "selected", False):
            return item
    return conversations[0]


def _snapshot_time(snapshot) -> str:
    captured_at = getattr(getattr(snapshot, "window", None), "captured_at", "")
    if "T" in captured_at:
        return captured_at.split("T", 1)[1][:5]
    return captured_at[:5] or "未知"
