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

from geopy.distance import geodesic
import re
import json
from collections import OrderedDict


class DataProcessor:
    @staticmethod
    def process(raw_data, config):
        """
        完整数据处理入口
        :param raw_data: API原始数据
        :param config: 配置文件
        :return: OrderedDict 有序结果
        """
        processed = OrderedDict()
        enabled_fields = DataProcessor._get_enabled_fields(config)

        for address_name, data in raw_data.items():
            processed[address_name] = OrderedDict()
            processed[address_name]["名称"] = data.get("title", address_name)

            # 按显示顺序处理每个启用字段
            for field_config in enabled_fields:
                field_name = field_config["name"]
                handler = DataProcessor._get_field_handler(field_name)
                raw_value = data["field_data"].get(field_name)

                result = handler(
                    raw_value=raw_value,
                    base_coord=data["coordinates"],
                    district=data.get("district", ""),
                    config=config,
                    field_config=field_config,
                    formatted_address=data.get("formatted_address", address_name),
                    address_name=address_name
                )
                processed[address_name][field_name] = result

        return processed

    @staticmethod
    def _get_enabled_fields(config):
        """获取并排序已启用的字段配置"""
        enabled = [item for item in config["config"]["items"] if item["enabled"]]
        return sorted(enabled, key=lambda x: x["display_index"])

    @staticmethod
    def _get_field_handler(field_name):
        """字段处理路由（统一参数适配）"""
        return {
            # 距离类字段（全部添加 lambda **kw:）
            "距轨道站点距离（米）": lambda **kw: DataProcessor._handle_rail_distance(**kw),
            "距最近商服中心的距离(公里)": lambda **kw: DataProcessor._handle_commercial_center(**kw),
            "距公交站点距离（米）": lambda **kw: DataProcessor._handle_bus_station(**kw),
            "公用设施条件(公里)": lambda **kw: DataProcessor._handle_public_facility(**kw),
            "距商务中心的距离(公里)": lambda **kw: DataProcessor._handle_business_center(**kw),
            "距火车站的距离(公里)": lambda **kw: DataProcessor._handle_train_station(**kw),
            "距最近货运火车站的距离(公里)": lambda **kw: DataProcessor._handle_freight_train(**kw),
            "距最近货运港口的距离(公里)": lambda **kw: DataProcessor._handle_freight_port(**kw),
            "距长途车站/客运站点距离(公里)": lambda **kw: DataProcessor._handle_bus_terminal(**kw),
            "距机场的距离(公里)": lambda **kw: DataProcessor._handle_airport(**kw),
            "距高速公路出入口的距离(公里)": lambda **kw: DataProcessor._handle_highway_exit(**kw),

            # 其他字段（全部添加 lambda **kw:）
            "商服网点聚集程度": lambda **kw: DataProcessor._handle_commercial_density(**kw),
            "商务聚集程度": lambda **kw: DataProcessor._handle_business_density(**kw),
            "客流数量": lambda **kw: DataProcessor._handle_passenger_flow(**kw),
            "居住氛围": lambda **kw: DataProcessor._handle_residential(**kw),
            "道路通达程度": lambda **kw: DataProcessor._handle_road_condition(**kw),
            "临街（路）状况": lambda **kw: DataProcessor._handle_street_condition(**kw),
            "X米半径范围内公共交通线路数": lambda **kw: DataProcessor._handle_public_transit(**kw),

            # 基础字段
            "位置": lambda **kw: kw.get("formatted_address", kw.get("address_name", "")),
        }.get(field_name, lambda **kw: "字段处理未实现")

    # --------------------------
    # 距离类字段完整实现
    # --------------------------
    @staticmethod
    def _handle_rail_distance(raw_value, base_coord, config, field_config, **kwargs):
        return DataProcessor._generic_distance_handler(
            poi_list=raw_value,
            base_coord=base_coord,
            config=config,
            field_config=field_config,
            poi_type="地铁站"
        )

    @staticmethod
    def _handle_commercial_center(raw_value, base_coord, config, field_config, **kwargs):
        return DataProcessor._generic_distance_handler(
            poi_list=raw_value,
            base_coord=base_coord,
            config=config,
            field_config=field_config,
            poi_type="商场"
        )

    @staticmethod
    def _handle_bus_station(raw_value, base_coord, config, field_config, **kwargs):
        return DataProcessor._generic_distance_handler(
            poi_list=raw_value,
            base_coord=base_coord,
            config=config,
            field_config=field_config,
            poi_type="公交站"
        )

    @staticmethod
    def _handle_business_center(raw_value, base_coord, config, field_config, **kwargs):
        return DataProcessor._generic_distance_handler(
            poi_list=raw_value,
            base_coord=base_coord,
            config=config,
            field_config=field_config,
            poi_type="商务中心"
        )

    @staticmethod
    def _handle_train_station(raw_value, base_coord, config, field_config, **kwargs):
        return DataProcessor._generic_distance_handler(
            poi_list=raw_value,
            base_coord=base_coord,
            config=config,
            field_config=field_config,
            poi_type="火车站"
        )

    @staticmethod
    def _handle_freight_train(raw_value, base_coord, config, field_config, **kwargs):
        return DataProcessor._generic_distance_handler(
            poi_list=raw_value,
            base_coord=base_coord,
            config=config,
            field_config=field_config,
            poi_type="货运站"
        )

    @staticmethod
    def _handle_freight_port(raw_value, base_coord, config, field_config, **kwargs):
        return DataProcessor._generic_distance_handler(
            poi_list=raw_value,
            base_coord=base_coord,
            config=config,
            field_config=field_config,
            poi_type="货运港口"
        )

    @staticmethod
    def _handle_bus_terminal(raw_value, base_coord, config, field_config, **kwargs):
        return DataProcessor._generic_distance_handler(
            poi_list=raw_value,
            base_coord=base_coord,
            config=config,
            field_config=field_config,
            poi_type="长途汽车站"
        )

    @staticmethod
    def _handle_airport(raw_value, base_coord, config, field_config, **kwargs):
        return DataProcessor._generic_distance_handler(
            poi_list=raw_value,
            base_coord=base_coord,
            config=config,
            field_config=field_config,
            poi_type="机场"
        )

    @staticmethod
    def _handle_highway_exit(raw_value, base_coord, config, field_config, **kwargs):
        return DataProcessor._generic_distance_handler(
            poi_list=raw_value,
            base_coord=base_coord,
            config=config,
            field_config=field_config,
            poi_type="高速出口"
        )

    # --------------------------
    # 聚集类字段完整实现
    # --------------------------
    @staticmethod
    def _handle_commercial_density(raw_value, **kwargs):
        """商服网点聚集程度"""
        categories = ["商场", "超市", "便利店"]
        names = set()

        for cat in categories:
            if poi := DataProcessor._get_nearest_poi(raw_value.get(cat, [])):
                names.add(poi["name"])

        if not names:
            return "无商服网点"
        samples = list(names)[:3]
        return f"周边有{'、'.join(samples)}等商服网点"

    @staticmethod
    def _handle_business_density(raw_value, **kwargs):
        """商务聚集程度"""
        pois = DataProcessor._get_nearest_poi(raw_value)
        if not pois:
            return "无商务中心"
        return f"周边有{pois['name']}等商务中心"

    # --------------------------
    # 其他字段完整实现
    # --------------------------
    @staticmethod
    def _handle_passenger_flow(raw_value, district, **kwargs):
        """客流数量"""
        if school_poi := DataProcessor._get_nearest_poi(raw_value):
            return f"位于{district}，靠近{school_poi['name']}"
        return f"位于{district}"

    @staticmethod
    def _handle_residential(raw_value, **kwargs):
        """居住氛围"""
        pois = sorted(raw_value,
                      key=lambda x: x["detail_info"].get("distance", float("inf")))[:2]
        return f"周边有{'、'.join(p['name'] for p in pois)}等居住小区" if pois else "无居住小区"

    @staticmethod
    def _handle_road_condition(raw_value, **kwargs):
        """道路通达程度"""
        roads = list({p["name"] for p in raw_value[:2]})
        return f"周边有{'、'.join(roads)}" if roads else "无道路信息"

    @staticmethod
    def _handle_street_condition(raw_value, **kwargs):
        """临街（路）状况"""
        return DataProcessor._handle_road_condition(raw_value)  # 逻辑相同

    @staticmethod
    def _handle_public_transit(raw_value, **kwargs):
        """X米半径范围内公共交通线路数"""

        lines = set()
        for poi in raw_value:
            if match := re.findall(r"\d+路", poi["address"]):
                lines.update(match)

        return f"附近有{'、'.join(sorted(lines)[:5])}等{len(lines)}条公交线路" if lines else "无公交线路"

    @staticmethod
    def _handle_public_facility(raw_value, base_coord, config, field_config,**kwargs):
        """公用设施条件(公里)"""
        categories = ["医院", "学校", "银行", "公园"]
        valid_pois = []
        total_distance = 0

        for cat in categories:
            if poi := DataProcessor._get_nearest_poi(raw_value.get(cat, [])):
                distance = DataProcessor._calculate_distance(base_coord, poi["location"])
                valid_pois.append(poi)
                total_distance += distance

        if not valid_pois:
            return "无公用设施"

        avg_distance = total_distance / len(valid_pois)
        converted_avg = DataProcessor._convert_distance(avg_distance, "公里")

        samples = [poi["name"] for poi in valid_pois[:4]]
        text = f"周边有{'、'.join(samples)}等，平均距离{converted_avg}"

        rules = config["config"]["comparisons"].get(str(field_config["original_index"]), {})
        level = DataProcessor._apply_comparison(converted_avg, rules)
        return f"{text}，{level}" if level else text

    # --------------------------
    # 核心工具方法
    # --------------------------
    @staticmethod
    def _generic_distance_handler(poi_list, base_coord, config, field_config, poi_type="POI"):
        """通用距离处理模板"""
        if not poi_list:
            return f"无{poi_type}"

        poi = DataProcessor._get_nearest_poi(poi_list)
        actual_dist = DataProcessor._calculate_distance(base_coord, poi["location"])

        # 单位转换
        if "公里" in field_config["name"]:
            converted = f"{DataProcessor._round_to_km(actual_dist)}公里"
        else:
            converted = f"{DataProcessor._round_to_meter(actual_dist)}米"

        # 构建文本
        text = f"距离{poi['name']}{converted}"

        # 应用比较规则
        rules = config["config"]["comparisons"].get(str(field_config["original_index"]), {})
        level = DataProcessor._apply_comparison(converted, rules)
        return f"{text}，{level}" if level else text

    @staticmethod
    def _get_nearest_poi(poi_list):
        """获取距离最近的POI"""
        if not poi_list:
            return None
        return min(
            poi_list,
            key=lambda x: x["detail_info"].get("distance", float("inf")),
            default=None
        )

    @staticmethod
    def _calculate_distance(coord1, location_dict):
        """精确球面距离计算（米）"""
        coord2 = (location_dict["lng"], location_dict["lat"])
        return geodesic(
            (coord1[1], coord1[0]),  # (纬度, 经度)
            (coord2[1], coord2[0])
        ).meters

    @staticmethod
    def _round_to_km(meters):
        """米转公里（保留1位小数，十位舍入）"""
        return round(meters / 1000, 1)

    @staticmethod
    def _round_to_meter(meters):
        """整百舍入（1234→1200，1250→1300）"""
        return int(round(meters / 100) * 100)

    @staticmethod
    def _convert_distance(meters, unit_type):
        """单位转换"""
        if unit_type == "公里":
            return f"{DataProcessor._round_to_km(meters)}公里"
        return f"{DataProcessor._round_to_meter(meters)}米"

    @staticmethod
    def _apply_comparison(converted_text, rules):
        """应用比较规则（左闭右开区间）"""
        # 提取数值和单位
        match = re.match(r"(\d+\.?\d*)(公里|米)", converted_text)
        if not match:
            return ""

        value = float(match.group(1))
        unit = match.group(2)

        for level, condition in rules.items():
            min_val = condition.get("min")
            max_val = condition.get("max")

            # 边界判断
            lower_ok = (min_val is None) or (value >= min_val)
            upper_ok = (max_val is None) or (value < max_val)

            if lower_ok and upper_ok:
                return level
        return ""
