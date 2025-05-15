# Copyright 2023 agenius666
# GitHub: https://github.com/agenius666/BaiduMap-SearchTool
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from api_client import BaiduMapClient
from data_processor import DataProcessor
from excel_report_writer import ExcelWriter
import sys
import json
import base64
import webbrowser
import pandas as pd
import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QCheckBox, QLineEdit, QPushButton,
    QFileDialog, QLabel, QGroupBox, QScrollArea, QMessageBox, QGridLayout
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QDoubleValidator, QIntValidator, QIcon, QPixmap

# 配置参数
CURRENT_VERSION = ""
UPDATE_CHECK_URL = ""
USER_MANUAL_URL = ""
ICON_BASE64 = ""

# 字段配置
FIELD_DEFINITIONS = [
    (0, '位置', False),
    (1, '距最近商服中心的距离(公里)', True),
    (2, '商服网点聚集程度', True),
    (3, '客流数量', True),
    (4, '居住氛围', True),
    (5, '道路通达程度', True),
    (6, '临街（路）状况', True),
    (7, 'X米半径范围内公共交通线路数', True),
    (8, '距公交站点距离（米）', True),
    (9, '距轨道站点距离（米）', True),
    (10, '公用设施条件(公里)', True),
    (11, '距商务中心的距离(公里)', True),
    (12, '商务聚集程度', True),
    (13, '距火车站的距离(公里)', True),
    (14, '距最近货运火车站的距离(公里)', True),
    (15, '距最近货运港口的距离(公里)', True),
    (16, '距长途车站/客运站点距离(公里)', True),
    (17, '距机场的距离(公里)', True),
    (18, '距高速公路出入口的距离(公里)', True)
]

COMPARE_FIELDS = {
    '距最近商服中心的距离(公里)',
    'X米半径范围内公共交通线路数',
    '距公交站点距离（米）',
    '距轨道站点距离（米）',
    '公用设施条件(公里)',
    '距商务中心的距离(公里)',
    '距火车站的距离(公里)',
    '距最近货运火车站的距离(公里)',
    '距最近货运港口的距离(公里)',
    '距长途车站/客运站点距离(公里)',
    '距机场的距离(公里)',
    '距高速公路出入口的距离(公里)'
}

COMPARE_LEVELS = ['优', '较优', '一般', '较差', '差']


class WorkerSignals(QObject):
    progress = Signal(int, str)
    finished = Signal(bool)
    error = Signal(str)


class WorkerThread(QThread):
    def __init__(self, config, template_path, output_file):
        super().__init__()
        self.config = config
        self.template_path = template_path
        self.output_file = output_file
        self.signals = WorkerSignals()
        self.raw_data = {}
        self.total_groups = 0  

    def run(self):
        try:
            client = BaiduMapClient(self.config["config"]["ak"])
            template_df = pd.read_excel(self.template_path)
            addresses = template_df['小区'].unique()
            total_addresses = len(addresses)

            for idx, address in enumerate(addresses, 1):
                raw = client.get_location_data(address, self.config["config"]["items"])
                if raw:
                    self.raw_data[address] = raw
                # 实时进度计算
                progress = int(idx / total_addresses * 70)
                self.signals.progress.emit(
                    progress,
                    f"获取数据({idx}/{total_addresses}): {address[:10]}..."
                )

            self.signals.progress.emit(70, "数据加工中...")
            processed_data = DataProcessor.process(self.raw_data, self.config)

            template_df = pd.read_excel(self.template_path)
            self.total_groups = len(template_df.groupby('分组'))
            self.signals.progress.emit(90, f"准备生成{self.total_groups}个分组")

            self.signals.progress.emit(90, "开始生成Excel文件...")
            ExcelWriter.write(
                self.output_file,
                processed_data,
                self.template_path,
                self.config,
                progress_callback=self._update_excel_progress  # 绑定回调
            )

            self.signals.progress.emit(100, "处理完成")
            self.signals.finished.emit(True)

        except Exception as e:
            self.signals.error.emit(f"处理失败: {str(e)}")
            import traceback
            traceback.print_exc()

    def _update_excel_progress(self, current, total):
        """Excel生成进度回调"""
        percent = 90 + int(current / total * 10)
        self.signals.progress.emit(
            percent,
            f"正在生成分组{current}/{total}"
        )


class CompareRuleWidget(QWidget):
    def __init__(self, original_index, parent=None):
        super().__init__(parent)
        self.original_index = original_index
        self.field_name = FIELD_DEFINITIONS[original_index][1]
        layout = QGridLayout()

        # 表头
        layout.addWidget(QLabel("等级"), 0, 0)
        layout.addWidget(QLabel("最小值"), 0, 1)
        layout.addWidget(QLabel("最大值"), 0, 2)

        # 输入行
        self.inputs = {}
        for row, level in enumerate(COMPARE_LEVELS, 1):
            layout.addWidget(QLabel(level), row, 0)

            min_input = QLineEdit()
            min_input.setValidator(QDoubleValidator())
            min_input.setFixedWidth(80)

            max_input = QLineEdit()
            max_input.setValidator(QDoubleValidator())
            max_input.setFixedWidth(80)

            layout.addWidget(min_input, row, 1)
            layout.addWidget(QLabel("<"), row, 2, alignment=Qt.AlignCenter)
            layout.addWidget(max_input, row, 3)

            self.inputs[level] = (min_input, max_input)

        layout.setColumnStretch(4, 1)
        self.setLayout(layout)

    def get_values(self):
        rules = {}
        for level, (min_input, max_input) in self.inputs.items():
            min_val = min_input.text()
            max_val = max_input.text()
            try:
                rules[level] = {
                    "min": float(min_val) if min_val else None,
                    "max": float(max_val) if max_val else None
                }
                if rules[level]["min"] is not None and rules[level]["max"] is not None:
                    if rules[level]["min"] >= rules[level]["max"]:
                        return None, f"{self.field_name}的{level}范围无效"
            except ValueError:
                return None, f"{self.field_name}的{level}包含非法数值"
        return rules, ""


class ConfigItemWidget(QWidget):
    def __init__(self, original_index, parent=None):
        super().__init__(parent)
        self.original_index = original_index
        _, field_name, has_radius = FIELD_DEFINITIONS[original_index]
        layout = QHBoxLayout()
        layout.addWidget(QLabel(field_name))

        if has_radius:
            self.radius_input = QLineEdit()
            self.radius_input.setPlaceholderText("半径（米）")
            self.radius_input.setValidator(QIntValidator(100, 10000))
            self.radius_input.setFixedWidth(120)
            layout.addWidget(QLabel("半径:"))
            layout.addWidget(self.radius_input)
        else:
            self.radius_input = None

        layout.addStretch()
        self.setLayout(layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.input_file = None
        self.temp_config = {
            "original_order": [defn[0] for defn in FIELD_DEFINITIONS],
            "config": {
                "ak": "",
                "display_order": [defn[0] for defn in FIELD_DEFINITIONS],
                "items": [],
                "comparisons": {}
            }
        }
        self.field_configs = {}
        self.compare_rules = {}
        self.setWindowTitle("BaiduMap_SearchToolbox 1.0.0")
        self.setWindowIcon(self.create_icon())
        self.current_version = CURRENT_VERSION
        self.init_ui()
        self.init_fields()
        self.setMinimumSize(1280, 800)
        self.rebuild_config_panels()
        self.auto_check_update()

    def create_icon(self):
        try:
            icon_data = base64.b64decode(ICON_BASE64 + "=" * (4 - len(ICON_BASE64) % 4))
            pixmap = QPixmap()
            pixmap.loadFromData(icon_data)
            return QIcon(pixmap)
        except Exception:
            return QIcon()

    def init_ui(self):
        # 顶部工具栏
        top_bar = QHBoxLayout()

        # 左侧功能按钮
        left_tool = QHBoxLayout()
        self.btn_template = QPushButton("生成模板")
        self.btn_template.clicked.connect(self.create_template)
        self.btn_upload = QPushButton("上传文件")
        self.btn_upload.clicked.connect(self.upload_file)
        left_tool.addWidget(self.btn_template)
        left_tool.addWidget(self.btn_upload)
        top_bar.addLayout(left_tool)

        # AK输入
        top_bar.addWidget(QLabel("AK密钥:"))
        self.ak_input = QLineEdit()
        self.ak_input.textChanged.connect(lambda: self.temp_config["config"].__setitem__("ak", self.ak_input.text()))
        top_bar.addWidget(self.ak_input)

        # 右侧功能按钮
        right_tool = QHBoxLayout()
        self.btn_save = QPushButton("保存配置")
        self.btn_save.clicked.connect(self.save_temp_config)
        self.btn_export = QPushButton("导出配置")
        self.btn_export.clicked.connect(self.export_config)
        self.btn_import = QPushButton("导入配置")
        self.btn_import.clicked.connect(self.import_config)
        self.btn_update = QPushButton("检查更新")
        self.btn_update.clicked.connect(self.check_for_updates)
        self.btn_help = QPushButton("使用说明")
        self.btn_help.clicked.connect(self.open_user_manual)
        right_tool.addWidget(self.btn_save)
        right_tool.addWidget(self.btn_export)
        right_tool.addWidget(self.btn_import)
        right_tool.addWidget(self.btn_update)
        right_tool.addWidget(self.btn_help)
        top_bar.addLayout(right_tool)

        # 主内容区域
        main_content = QHBoxLayout()

        # 左侧字段列表
        left_panel = QGroupBox("选择字段（拖动排序）")
        left_panel.setMinimumWidth(280)
        self.field_list = QListWidget()
        self.field_list.setDragDropMode(QListWidget.InternalMove)
        self.field_list.model().rowsMoved.connect(self.handle_drag_drop)
        left_panel.setLayout(QVBoxLayout())
        left_panel.layout().addWidget(self.field_list)

        # 中间配置区域
        center_panel = QGroupBox("检索参数设置")
        self.config_scroll = QScrollArea()
        self.config_scroll.setWidgetResizable(True)
        self.config_content = QWidget()
        self.config_content.setLayout(QVBoxLayout())
        self.config_scroll.setWidget(self.config_content)
        center_panel.setLayout(QVBoxLayout())
        center_panel.layout().addWidget(self.config_scroll)

        # 右侧比较规则
        right_panel = QGroupBox("比较规则设置")
        right_panel.setMinimumWidth(600)
        self.compare_scroll = QScrollArea()
        self.compare_scroll.setWidgetResizable(True)
        self.compare_content = QWidget()
        self.compare_content.setLayout(QVBoxLayout())
        self.compare_scroll.setWidget(self.compare_content)
        right_panel.setLayout(QVBoxLayout())
        right_panel.layout().addWidget(self.compare_scroll)

        # 组装主界面
        main_content.addWidget(left_panel)
        main_content.addWidget(center_panel)
        main_content.addWidget(right_panel)

        # 底部按钮
        self.btn_process = QPushButton("开始处理")
        self.btn_process.clicked.connect(self.start_processing)

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addLayout(top_bar)
        main_layout.addLayout(main_content)
        main_layout.addWidget(self.btn_process)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def init_fields(self):
        for original_index in self.temp_config["config"]["display_order"]:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, original_index)
            widget = QWidget()
            layout = QHBoxLayout(widget)
            check = QCheckBox(FIELD_DEFINITIONS[original_index][1])
            layout.addWidget(check)
            layout.addStretch()
            item.setSizeHint(widget.sizeHint())
            self.field_list.addItem(item)
            self.field_list.setItemWidget(item, widget)
            # 初始化配置存储为None
            self.field_configs[original_index] = {
                "enabled": False,
                "radius": None
            }

    def handle_drag_drop(self):
        self.save_current_configs()
        print(json.dumps(self.temp_config, indent=2, ensure_ascii=False))
        self.update_display_order()
        self.rebuild_config_panels()

    def save_current_configs(self):
        """实时同步所有UI状态到内存"""
        try:

            for i in range(self.field_list.count()):
                item = self.field_list.item(i)
                if not item:  
                    continue

                original_index = item.data(Qt.UserRole)
                widget = self.field_list.itemWidget(item)

                if widget:

                    checkboxes = widget.findChildren(QCheckBox)
                    if checkboxes:
                        self.field_configs[original_index]["enabled"] = checkboxes[0].isChecked()


            if self.config_content.layout():
                for i in range(self.config_content.layout().count()):
                    layout_item = self.config_content.layout().itemAt(i)
                    if not layout_item:  # 检查布局项是否存在
                        continue

                    widget = layout_item.widget()
                    if not widget:  # 检查控件是否存在
                        continue

                    # 使用getattr避免属性不存在
                    radius_input = getattr(widget, 'radius_input', None)
                    original_index = getattr(widget, 'original_index', None)

                    if radius_input and original_index is not None:
                        try:
                            text = radius_input.text().strip()
                            self.field_configs[original_index]["radius"] = int(text) if text.isdigit() else None
                        except ValueError:
                            print(f"无效的半径值: {text}")
                        except AttributeError:
                            print(f"字段 {original_index} 的半径输入框异常")


            self.compare_rules.clear()
            if self.compare_content.layout():
                for i in range(self.compare_content.layout().count()):
                    layout_item = self.compare_content.layout().itemAt(i)
                    if not layout_item:
                        continue

                    group = layout_item.widget()
                    if not isinstance(group, QGroupBox):
                        continue


                    compare_widget = next((w for w in group.findChildren(CompareRuleWidget)), None)
                    if not compare_widget:
                        continue

                    try:
                        original_index = compare_widget.original_index
                        rules = {}
                        for level in COMPARE_LEVELS:
                            inputs = compare_widget.inputs.get(level, (None, None))
                            min_input, max_input = inputs

                            # 获取文本值
                            min_text = min_input.text().strip() if min_input else ""
                            max_text = max_input.text().strip() if max_input else ""

                            # 类型转换
                            rules[level] = {
                                "min": float(min_text) if min_text else None,
                                "max": float(max_text) if max_text else None
                            }
                        self.compare_rules[original_index] = rules
                    except Exception as e:
                        print(f"比较规则同步失败: {str(e)}")

        except Exception as e:
            print(f"配置保存异常: {str(e)}")
            raise

    def update_display_order(self):
        self.temp_config["config"]["display_order"] = [
            self.field_list.item(i).data(Qt.UserRole)
            for i in range(self.field_list.count())
        ]

    def rebuild_config_panels(self):
        # 清空现有组件
        while self.config_content.layout().count() > 0:
            self.config_content.layout().takeAt(0).widget().deleteLater()
        while self.compare_content.layout().count() > 0:
            self.compare_content.layout().takeAt(0).widget().deleteLater()

        # 重建检索参数面板
        for original_index in self.temp_config["config"]["display_order"]:
            config_widget = ConfigItemWidget(original_index)
            if config_widget.radius_input:
                radius_value = self.field_configs[original_index]["radius"]
                # None显示为空字符串
                display_text = str(radius_value) if radius_value is not None else ""
                config_widget.radius_input.setText(display_text)
            self.config_content.layout().addWidget(config_widget)

        # 重建比较规则面板
        for original_index in self.temp_config["config"]["display_order"]:
            _, field_name, _ = FIELD_DEFINITIONS[original_index]
            if field_name in COMPARE_FIELDS:
                group = QGroupBox(field_name)
                compare_widget = CompareRuleWidget(original_index)
                if original_index in self.compare_rules:
                    rules = self.compare_rules[original_index]
                    for level in COMPARE_LEVELS:
                        min_val = str(rules.get(level, {}).get("min", "")) if rules.get(level, {}).get("min") else ""
                        max_val = str(rules.get(level, {}).get("max", "")) if rules.get(level, {}).get("max") else ""
                        compare_widget.inputs[level][0].setText(min_val)
                        compare_widget.inputs[level][1].setText(max_val)
                group.setLayout(QVBoxLayout())
                group.layout().addWidget(compare_widget)
                self.compare_content.layout().addWidget(group)

        # 恢复启用状态
        for i in range(self.field_list.count()):
            original_index = self.field_list.item(i).data(Qt.UserRole)
            widget = self.field_list.itemWidget(self.field_list.item(i))
            widget.findChild(QCheckBox).setChecked(self.field_configs[original_index]["enabled"])

    def save_temp_config(self):
        """保存配置到临时结构，始终以当前UI状态为准"""
        try:
            # 强制同步最新UI状态
            self.save_current_configs()

            # 构建可序列化的配置项
            self.temp_config["config"]["items"] = []
            for original_index, config in self.field_configs.items():
                # 直接从内存获取最新数据
                self.temp_config["config"]["items"].append({
                    "original_index": original_index,
                    "display_index": next((i for i, idx in enumerate(self.temp_config["config"]["display_order"])
                                           if idx == original_index), -1),
                    "name": FIELD_DEFINITIONS[original_index][1],
                    "enabled": config["enabled"],
                    "radius": config["radius"]
                })

            # 序列化比较规则
            serialized_comparisons = {}
            for field_id, levels in self.compare_rules.items():
                serialized_levels = {}
                for level_name, rules in levels.items():
                    # 确保数值类型正确
                    serialized_levels[level_name] = {
                        "min": float(rules["min"]) if rules["min"] is not None else None,
                        "max": float(rules["max"]) if rules["max"] is not None else None
                    }
                serialized_comparisons[str(field_id)] = serialized_levels

            self.temp_config["config"]["comparisons"] = serialized_comparisons

            QMessageBox.information(self, "成功", "配置已保存")

        except ValueError as ve:
            QMessageBox.critical(self, "数值错误", f"非法数值输入: {str(ve)}")
        except Exception as e:
            error_msg = f"保存失败: {str(e)}\n追踪信息:\n{traceback.format_exc()}"
            QMessageBox.critical(self, "系统错误", error_msg)

    def export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存配置文件", "", "JSON文件 (*.json)")
        if path:
            try:
                with open(path, "w", encoding='utf-8') as f:
                    json.dump(self.temp_config, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "成功", "配置导出成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def import_config(self):
        """导入配置时完全重建UI状态"""
        path, _ = QFileDialog.getOpenFileName(self, "选择配置文件", "", "JSON文件 (*.json)")
        if path:
            try:
                with open(path, "r", encoding='utf-8') as f:
                    import_data = json.load(f)

                # 使用临时变量防止导入失败污染现有配置
                temp_field_configs = {}
                temp_compare_rules = {}
                temp_display_order = []

                # 验证必要字段
                if "config" not in import_data:
                    raise ValueError("无效的配置文件格式")

                # 处理字段显示顺序
                temp_display_order = import_data["config"].get("display_order", [])

                # 导入字段配置
                for item in import_data["config"].get("items", []):
                    original_index = item.get("original_index")
                    if original_index is None:
                        continue

                    # 处理旧版本配置兼容
                    radius_value = item.get("radius", 0)  # 兼容旧版本默认值
                    if radius_value == 0 and "radius" not in item:
                        radius_value = None

                    temp_field_configs[original_index] = {
                        "enabled": item.get("enabled", False),
                        "radius": radius_value
                    }

                # 导入比较规则
                for str_id, levels in import_data["config"].get("comparisons", {}).items():
                    try:
                        field_id = int(str_id)
                        processed_levels = {}
                        for level_name, rules in levels.items():
                            # 转换JSON null为Python None
                            processed_levels[level_name] = {
                                "min": rules.get("min"),
                                "max": rules.get("max")
                            }
                        temp_compare_rules[field_id] = processed_levels
                    except (ValueError, TypeError) as e:
                        print(f"跳过无效的比较规则字段ID: {str_id}, 错误: {str(e)}")

                # 原子化更新配置
                self.temp_config = import_data
                self.field_configs = temp_field_configs
                self.compare_rules = temp_compare_rules
                self.ak_input.setText(import_data["config"].get("ak", ""))

                # 强制完全重建界面
                self.rebuild_interface()

                QMessageBox.information(self, "成功", "配置导入完成")

            except json.JSONDecodeError as je:
                error_msg = f"JSON解析失败: {str(je)}\n错误位置: 第{je.lineno}行, 列{je.colno}"
                QMessageBox.critical(self, "格式错误", error_msg)
            except Exception as e:
                error_msg = f"导入失败: {str(e)}\n追踪信息:\n{traceback.format_exc()}"
                QMessageBox.critical(self, "系统错误", error_msg)

    def rebuild_interface(self):
        self.field_list.clear()
        for original_index in self.temp_config["config"]["display_order"]:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, original_index)
            widget = QWidget()
            layout = QHBoxLayout(widget)
            check = QCheckBox(FIELD_DEFINITIONS[original_index][1])
            check.setChecked(self.field_configs.get(original_index, {}).get("enabled", False))
            layout.addWidget(check)
            layout.addStretch()
            item.setSizeHint(widget.sizeHint())
            self.field_list.addItem(item)
            self.field_list.setItemWidget(item, widget)
        self.rebuild_config_panels()

    def create_template(self):
        try:
            path, _ = QFileDialog.getSaveFileName(self, "保存模板文件", "", "Excel文件 (*.xlsx)")
            if path:
                import pandas as pd
                example_data = [
                    ['分组', '小区', '类型'],
                    [1, '示例小区1', '案例小区'],
                    [1, '示例小区2', '可比对象A'],
                    [2, '示例小区3', '案例小区']
                ]
                df = pd.DataFrame(example_data[1:], columns=example_data[0])
                df.to_excel(path, index=False)
                QMessageBox.information(self, "成功", "模板文件生成成功")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成模板失败: {str(e)}")

    def upload_file(self):
        self.input_file, _ = QFileDialog.getOpenFileName(self, "选择Excel文件", "", "Excel文件 (*.xlsx *.xls)")
        if self.input_file:
            QMessageBox.information(self, "成功", f"已选择文件: {self.input_file}")

    def validate_config(self):
        """配置验证方法"""
        required_fields = [defn[1] for defn in FIELD_DEFINITIONS if defn[2]]  
        for item in self.temp_config["config"]["items"]:
            if item["enabled"] and item["name"] in required_fields:
                if item.get("radius") is None:
                    QMessageBox.critical(
                        self,
                        "参数缺失",
                        f"字段【{item['name']}】需要填写半径参数！"
                    )
                    return False
        return True

    def start_processing(self):
        self.save_temp_config()
        if not self.validate_config():  
            return
        if not self.temp_config["config"]["ak"]:
            QMessageBox.critical(self, "错误", "请先输入百度地图AK")
            return
        if not self.input_file:
            QMessageBox.critical(self, "错误", "请先上传文件")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "保存结果", "", "Excel文件 (*.xlsx)")
        if save_path:
            self.worker = WorkerThread(self.temp_config, self.input_file, save_path)
            self.worker.signals.progress.connect(self.update_progress)
            self.worker.signals.finished.connect(lambda: self.btn_process.setEnabled(True))
            self.worker.signals.error.connect(self.handle_error)
            self.worker.start()
            self.btn_process.setEnabled(False)

    def update_progress(self, percent, message):
        self.btn_process.setText(f"处理中... {percent}% ({message})")

    def handle_error(self, message):
        QMessageBox.critical(self, "错误", message)
        self.btn_process.setEnabled(True)
        self.btn_process.setText("开始处理")

    def auto_check_update(self):
        try:
            response = requests.get(UPDATE_CHECK_URL, timeout=5)
            version_info = response.json()
            if self.compare_versions(CURRENT_VERSION, version_info["latestVersion"]) < 0:
                if QMessageBox.Yes == QMessageBox.question(self, "更新",
                                                           f"发现新版本 {version_info['latestVersion']}，是否下载？"):
                    webbrowser.open(version_info["updateUrl"])
        except Exception as e:
            print(f"更新检查失败: {str(e)}")

    def compare_versions(self, v1, v2):
        v1_parts = list(map(int, v1.split('.')))
        v2_parts = list(map(int, v2.split('.')))
        for v1_part, v2_part in zip(v1_parts, v2_parts):
            if v1_part != v2_part:
                return v1_part - v2_part
        return 0

    def check_for_updates(self):
        self.auto_check_update()

    def open_user_manual(self):
        webbrowser.open(USER_MANUAL_URL)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
