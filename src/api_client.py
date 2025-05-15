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

import requests
import json
from geopy.distance import geodesic


class BaiduMapClient:
    def __init__(self, ak):
        self.ak = ak
        self.geocode_cache = {}
        self.poi_cache = {}

    def get_location_data(self, address, config_items):
        """
        获取原始API数据
        :return: {
            "coordinates": (lng, lat),
            "formatted_address": "详细地址",
            "field_data": {
                "距最近商服中心的距离(公里)": {API原始响应},
                "商服网点聚集程度": {"商场": [...], "超市": [...]},
                ...
            }
        }
        """
        # 地理编码
        coord = self._geocode(address)
        if not coord:
            return None

        # 反向地理编码获取详细地址
        address_info = self._reverse_geocode(coord)

        # 收集所有启用的字段数据
        field_data = {}
        for item in config_items:
            if item['enabled']:
                field_data[item['name']] = self._get_field_data(item, coord)

        return {
            "coordinates": coord,
            "formatted_address": address_info['formatted_address'],
            "district": address_info.get('district', ''),
            "field_data": field_data
        }

    def _geocode(self, address):
        """地理编码（带缓存）"""
        if address in self.geocode_cache:
            return self.geocode_cache[address]

        params = {
            "address": address,
            "output": "json",
            "ak": self.ak
        }
        try:
            response = requests.get("https://api.map.baidu.com/geocoding/v3", params=params)
            result = response.json()
            if result['status'] == 0:
                loc = result['result']['location']
                coord = (loc['lng'], loc['lat'])
                self.geocode_cache[address] = coord
                return coord
            return None
        except Exception as e:
            print(f"Geocoding error: {str(e)}")
            return None

    def _reverse_geocode(self, coord):
        """反向地理编码（带缓存）"""
        cache_key = f"rev|{coord[0]},{coord[1]}"
        if cache_key in self.poi_cache:
            return self.poi_cache[cache_key]

        params = {
            "location": f"{coord[1]},{coord[0]}",
            "output": "json",
            "ak": self.ak,
            "coordtype": "bd09ll"
        }
        try:
            response = requests.get("https://api.map.baidu.com/reverse_geocoding/v3", params=params)
            result = response.json()
            if result['status'] == 0:
                data = {
                    "formatted_address": result['result']['formatted_address'],
                    "district": result['result']['addressComponent']['district']
                }
                self.poi_cache[cache_key] = data
                return data
            return {}
        except Exception as e:
            print(f"Reverse geocode error: {str(e)}")
            return {}

    def _get_field_data(self, config_item, coord):
        """获取单个字段的原始数据"""
        field_name = config_item['name']
        radius = config_item.get('radius', 1000)

        # 字段处理映射
        handlers = {
            "位置": lambda: None,  # 由反向地理编码处理
            "距最近商服中心的距离(公里)": lambda: self._search_poi("商场", coord, radius),
            "商服网点聚集程度": lambda: {
                "商场": self._search_poi("商场", coord, radius),
                "超市": self._search_poi("超市", coord, radius),
                "便利店": self._search_poi("便利店", coord, radius)
            },
            "客流数量": lambda: self._search_poi("学校", coord, radius),
            "居住氛围": lambda: self._search_poi("小区", coord, radius),
            "道路通达程度": lambda: self._search_poi("道路", coord, radius),
            "临街（路）状况": lambda: self._search_poi("道路", coord, radius),
            "X米半径范围内公共交通线路数": lambda: self._search_poi("公交", coord, radius),
            "距公交站点距离（米）": lambda: self._search_poi("公交站", coord, radius),
            "距轨道站点距离（米）": lambda: self._search_poi("地铁站", coord, radius),
            "公用设施条件(公里)": lambda: {
                "医院": self._search_poi("医院", coord, radius),
                "学校": self._search_poi("学校", coord, radius),
                "银行": self._search_poi("银行", coord, radius),
                "公园": self._search_poi("公园", coord, radius)
            },
            "距商务中心的距离(公里)": lambda: self._search_poi("商务中心", coord, radius),
            "商务聚集程度": lambda: self._search_poi("写字楼", coord, radius),
            "距火车站的距离(公里)": lambda: self._search_poi("火车站", coord, radius),
            "距最近货运火车站的距离(公里)": lambda: self._search_poi("货运站", coord, radius),
            "距最近货运港口的距离(公里)": lambda: self._search_poi("港口", coord, radius),
            "距长途车站/客运站点距离(公里)": lambda: self._search_poi("汽车站", coord, radius),
            "距机场的距离(公里)": lambda: self._search_poi("机场", coord, radius),
            "距高速公路出入口的距离(公里)": lambda: self._search_poi("高速出口", coord, radius)
        }

        return handlers[field_name]()
        print(f"API原始响应: {json.dumps(result, ensure_ascii=False)}")

    def _search_poi(self, query, coord, radius):
        """POI搜索（带缓存）"""
        cache_key = f"{query}|{coord}|{radius}"
        if cache_key in self.poi_cache:
            return self.poi_cache[cache_key]

        params = {
            "query": query,
            "location": f"{coord[1]},{coord[0]}",
            "radius": radius,
            "output": "json",
            "ak": self.ak,
            "scope": 2
        }
        try:
            response = requests.get("https://api.map.baidu.com/place/v2/search", params=params)
            result = response.json()
            if result['status'] == 0:
                # 按距离排序
                sorted_pois = sorted(
                    result['results'],
                    key=lambda x: x['detail_info'].get('distance', float('inf'))
                )
                self.poi_cache[cache_key] = sorted_pois
                return sorted_pois
            return []
        except Exception as e:
            print(f"POI search error: {str(e)}")
            return []
