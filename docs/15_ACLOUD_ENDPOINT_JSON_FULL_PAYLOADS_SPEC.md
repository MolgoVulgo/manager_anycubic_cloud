### But
Documenter l'integralite des valeurs JSON retournees par les endpoints Anycubic Cloud, a partir des captures disponibles (logs + HAR + code).

### Sources analysees
- Logs HTTP: `<LOCAL_PATH> Files/AnycubicPhotonWorkshop/Log/cloud_Log.log`
- Logs HTTP: `<LOCAL_PATH> Files/AnycubicPhotonWorkshop/Log/cloud_Log.log.1`
- HAR: `<LOCAL_PATH>
- Code endpoints: `<LOCAL_PATH>
- Code endpoints (legacy): `<LOCAL_PATH>
- Modeles attendus: `<LOCAL_PATH>

### Notes
- Les valeurs sensibles (token/cookie/signature/nonce/timestamp/email) sont masquées (dont `XX-Token`, `XX-Signature`, `XX-Nonce`, `XX-Timestamp`, `Cookie`, `Set-Cookie`).
- `__json` indique un champ string qui contient un JSON serialise.
- Quand un endpoint n est pas capture dans logs/HAR, le modele vient de `api_map.json` (si disponible).

### `POST /j/p/buried/buried/report`
- Capture: oui (2 echantillon(s))
- Sources: har:uc.makeronline.com.har x2
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=200
  - `msg` (str) example="success"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 200,
  "msg": "success"
}
```

### `GET /p/p/workbench/api/api/work/gcode/info`
- Capture: non
- Modele JSON attendu (source `api_map.json`):
```json
{
  "code": 1,
  "data": "<gcode info object>"
}
```

### `GET /p/p/workbench/api/user/profile/userInfo`
- Capture: oui (1 echantillon(s))
- Sources: har:uc.makeronline.com.har x1
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (object)
  - `data.apply_designer_status` (int) example=0
  - `data.avatar` (str) example=""
  - `data.avatar_store_type` (int) example=0
  - `data.balance` (str) example="0.00"
  - `data.birthday` (str) example="1970-01-01"
  - `data.casdoor_user` (object)
  - `data.casdoor_user.avatar` (str) example="https:....png"
  - `data.casdoor_user.birthday` (str) example=""
  - `data.casdoor_user.casdoor_user_token` (str) example="eyJhbG...iWhU"
  - `data.casdoor_user.control_reason` (str) example=""
  - `data.casdoor_user.control_reason_map` (str) example=""
  - `data.casdoor_user.country_code` (str) example=""
  - `data.casdoor_user.created_time` (str) example="2024-02-19T20:49:45+08:00"
  - `data.casdoor_user.display_country_code` (str) example=""
  - `data.casdoor_user.display_name` (str) example="Molgo"
  - `data.casdoor_user.email` (str) example="d***d@zelisko.fr"
  - `data.casdoor_user.forbid_contest` (int) example=0
  - `data.casdoor_user.forbid_giving_gift` (int) example=0
  - `data.casdoor_user.forbid_model` (int) example=0
  - `data.casdoor_user.forbid_points` (int) example=0
  - `data.casdoor_user.forbid_points_consume` (int) example=0
  - `data.casdoor_user.forbid_post` (int) example=0
  - `data.casdoor_user.forbid_post_comment` (int) example=0
  - `data.casdoor_user.forbid_printfile` (int) example=0
  - `data.casdoor_user.forbid_publish_wish` (int) example=0
  - `data.casdoor_user.freeze_created_at` (str) example=""
  - `data.casdoor_user.freeze_cycle` (int) example=0
  - `data.casdoor_user.freeze_login` (int) example=0
  - `data.casdoor_user.freeze_remark` (str) example=""
  - `data.casdoor_user.gender` (str) example="1"
  - `data.casdoor_user.id` (str) example="e1bf0028-e708-4117-b18c-b692e6937e5a"
  - `data.casdoor_user.identity_id` (str) example="4106224"
  - `data.casdoor_user.integral` (int) example=1
  - `data.casdoor_user.introduction` (str) example=""
  - `data.casdoor_user.is_deleted` (int) example=0
  - `data.casdoor_user.is_freeze` (int) example=0
  - `data.casdoor_user.is_user_risk` (int) example=0
  - `data.casdoor_user.is_user_risk_user_white` (int) example=0
  - `data.casdoor_user.is_verify` (int) example=0
  - `data.casdoor_user.mirror_forbid_sync_points` (int) example=0
  - `data.casdoor_user.mold_is_demotion` (int) example=0
  - `data.casdoor_user.mold_is_review` (int) example=0
  - `data.casdoor_user.mold_publish_set_c` (int) example=0
  - `data.casdoor_user.owner` (str) example="anycubic"
  - `data.casdoor_user.phone` (str) example=""
  - `data.casdoor_user.print_type` (int) example=0
  - `data.casdoor_user.printer_id` (int) example=0
  - `data.casdoor_user.printfile_is_review` (int) example=0
  - `data.casdoor_user.revenue_coin` (int) example=0
  - `data.casdoor_user.signup_application` (str) example="ac_android"
  - `data.casdoor_user.signup_port` (str) example="Mobile"
  - `data.casdoor_user.signup_type` (str) example="email"
  - `data.casdoor_user.social_links` (null)
  - `data.casdoor_user.tag_at` (null)
  - `data.casdoor_user.token_coin` (int) example=0
  - `data.casdoor_user.unfreeze_time` (str) example=""
  - `data.casdoor_user.updated_time` (str) example="2025-03-13T20:22:15+08:00"
  - `data.casdoor_user.user_name` (str) example="Molgo"
  - `data.casdoor_user.user_remarks` (null)
  - `data.casdoor_user.user_risk_user_white` (null)
  - `data.casdoor_user.user_tag` (null)
  - `data.casdoor_user_id` (str) example="e1bf0028-e708-4117-b18c-b692e6937e5a"
  - `data.casdoor_user_token` (str) example="eyJhbG...iWhU"
  - `data.city` (str) example=""
  - `data.coin` (int) example=0
  - `data.country` (str) example=""
  - `data.country_type` (str) example="country"
  - `data.create_day_time` (int) example=1708358400
  - `data.create_time` (int) example=1708375785
  - `data.id` (int) example=94829
  - `data.ip_city` (str) example="0"
  - `data.ip_country` (str) example="\u6cd5\u56fd"
  - `data.ip_province` (str) example="0"
  - `data.is_inner` (int) example=0
  - `data.label` (list)
  - `data.label[]` (empty)
  - `data.last_login_ip` (str) example="82.64.136.10"
  - `data.last_login_time` (int) example=1771717986
  - `data.last_print_time` (int) example=0
  - `data.login_type` (int) example=0
  - `data.message_key` (str) example="13065ffa4f0cfd29322"
  - `data.mobile` (str) example=""
  - `data.mobile_country_code` (str) example="0"
  - `data.mobile_country_id` (int) example=0
  - `data.more` (list)
  - `data.more[]` (empty)
  - `data.new_message` (int) example=81
  - `data.professional` (str) example=""
  - `data.province` (str) example=""
  - `data.register_source` (int) example=1
  - `data.register_type` (int) example=1
  - `data.score` (int) example=0
  - `data.sex` (int) example=1
  - `data.signature` (str) example=""
  - `data.task_count` (int) example=0
  - `data.total` (object)
  - `data.total.favorite` (int) example=0
  - `data.total.like` (int) example=0
  - `data.total.post_count` (int) example=0
  - `data.tourist_device_id` (str) example="unkonw"
  - `data.type` (str) example="1"
  - `data.uploadsize_status` (object)
  - `data.uploadsize_status.total` (str) example="2GB"
  - `data.uploadsize_status.total_bytes` (int) example=2147483648
  - `data.uploadsize_status.used` (str) example="1.34GB"
  - `data.uploadsize_status.used_bytes` (int) example=1438133459
  - `data.user_activation_key` (str) example=""
  - `data.user_email` (str) example="d***d@zelisko.fr"
  - `data.user_login` (str) example=""
  - `data.user_nickname` (str) example="Molgo"
  - `data.user_pass` (str) example="###a375deb776fc685c8c143de84b5482aa"
  - `data.user_status` (int) example=1
  - `data.user_type` (int) example=2
  - `data.user_url` (str) example=""
  - `msg` (str) example="\u8fde\u63a5\u6210\u529f"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": {
    "apply_designer_status": 0,
    "avatar": "",
    "avatar_store_type": 0,
    "balance": "0.00",
    "birthday": "1970-01-01",
    "casdoor_user": {
      "avatar": "https:....png",
      "birthday": "",
      "casdoor_user_token": "eyJhbG...iWhU",
      "control_reason": "",
      "control_reason_map": "",
      "country_code": "",
      "created_time": "2024-02-19T20:49:45+08:00",
      "display_country_code": "",
      "display_name": "Molgo",
      "email": "d***d@zelisko.fr",
      "forbid_contest": 0,
      "forbid_giving_gift": 0,
      "forbid_model": 0,
      "forbid_points": 0,
      "forbid_points_consume": 0,
      "forbid_post": 0,
      "forbid_post_comment": 0,
      "forbid_printfile": 0,
      "forbid_publish_wish": 0,
      "freeze_created_at": "",
      "freeze_cycle": 0,
      "freeze_login": 0,
      "freeze_remark": "",
      "gender": "1",
      "id": "e1bf0028-e708-4117-b18c-b692e6937e5a",
      "identity_id": "4106224",
      "integral": 1,
      "introduction": "",
      "is_deleted": 0,
      "is_freeze": 0,
      "is_user_risk": 0,
      "is_user_risk_user_white": 0,
      "is_verify": 0,
      "mirror_forbid_sync_points": 0,
      "mold_is_demotion": 0,
      "mold_is_review": 0,
      "mold_publish_set_c": 0,
      "owner": "anycubic",
      "phone": "",
      "print_type": 0,
      "printer_id": 0,
      "printfile_is_review": 0,
      "revenue_coin": 0,
      "signup_application": "ac_android",
      "signup_port": "Mobile",
      "signup_type": "email",
      "social_links": null,
      "tag_at": null,
      "token_coin": 0,
      "unfreeze_time": "",
      "updated_time": "2025-03-13T20:22:15+08:00",
      "user_name": "Molgo",
      "user_remarks": null,
      "user_risk_user_white": null,
      "user_tag": null
    },
    "casdoor_user_id": "e1bf0028-e708-4117-b18c-b692e6937e5a",
    "casdoor_user_token": "eyJhbG...iWhU",
    "city": "",
    "coin": 0,
    "country": "",
    "country_type": "country",
    "create_day_time": 1708358400,
    "create_time": 1708375785,
    "id": 94829,
    "ip_city": "0",
    "ip_country": "\u6cd5\u56fd",
    "ip_province": "0",
    "is_inner": 0,
    "label": [],
    "last_login_ip": "82.64.136.10",
    "last_login_time": 1771717986,
    "last_print_time": 0,
    "login_type": 0,
    "message_key": "13065ffa4f0cfd29322",
    "mobile": "",
    "mobile_country_code": "0",
    "mobile_country_id": 0,
    "more": [],
    "new_message": 81,
    "professional": "",
    "province": "",
    "register_source": 1,
    "register_type": 1,
    "score": 0,
    "sex": 1,
    "signature": "",
    "task_count": 0,
    "total": {
      "favorite": 0,
      "like": 0,
      "post_count": 0
    },
    "tourist_device_id": "unkonw",
    "type": "1",
    "uploadsize_status": {
      "total": "2GB",
      "total_bytes": 2147483648,
      "used": "1.34GB",
      "used_bytes": 1438133459
    },
    "user_activation_key": "",
    "user_email": "d***d@zelisko.fr",
    "user_login": "",
    "user_nickname": "Molgo",
    "user_pass": "###a375deb776fc685c8c143de84b5482aa",
    "user_status": 1,
    "user_type": 2,
    "user_url": ""
  },
  "msg": "\u8fde\u63a5\u6210\u529f"
}
```

### `POST /p/p/workbench/api/v2/cloud_storage/lockStorageSpace`
- Capture: oui (5 echantillon(s))
- Sources: log:cloud_Log.log.1 x5
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (object)
  - `data.id` (int) example=41514789
  - `data.preSignUrl` (str) example="https:...d%3E"
  - `data.url` (str) example="https:...pwmb"
  - `msg` (str) example="????"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": {
    "id": 41514789,
    "preSignUrl": "https:...d%3E",
    "url": "https:...pwmb"
  },
  "msg": "????"
}
```

### `POST /p/p/workbench/api/v2/cloud_storage/unlockStorageSpace`
- Capture: non
- Modele JSON attendu (source `api_map.json`):
```json
{
  "code": 1,
  "data": ""
}
```

### `POST /p/p/workbench/api/v2/message/getMessages`
- Capture: oui (3 echantillon(s))
- Sources: log:cloud_Log.log.1 x3
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (list)
  - `data[]` (object)
  - `data[].content` (str) example="No new information"
  - `data[].count` (int) example=0
  - `data[].create_time` (int) example=0
  - `data[].newcount` (int) example=0
  - `data[].title` (str) example=""
  - `data[].type` (int) example=3
  - `msg` (str) example="?????"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": [
    {
      "content": "No new information",
      "count": 0,
      "create_time": 0,
      "newcount": 0,
      "title": "",
      "type": 3
    },
    {
      "content": "\"raven...ile.",
      "count": 77,
      "create_time": 1770805690,
      "newcount": 75,
      "title": "Print to terminate",
      "type": 1
    },
    {
      "content": "No new information",
      "count": 0,
      "create_time": 0,
      "newcount": 0,
      "title": "",
      "type": 5
    }
  ],
  "msg": "?????"
}
```

### `GET /p/p/workbench/api/v2/printer/info`
- Capture: oui (33 echantillon(s))
- Sources: log:cloud_Log.log x5, log:cloud_Log.log.1 x28
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (object)
  - `data.advance` (list)
  - `data.advance[]` (empty)
  - `data.base` (object)
  - `data.base.create_time` (int) example=1708449350
  - `data.base.description` (str) example="A7F6-B0FF-F706-3D49"
  - `data.base.firmware_version` (null)
  - `data.base.machine_mac` (str) example="6E-D0-8D-A8-5A-EE"
  - `data.base.material_type` (str) example="??"
  - `data.base.material_used` (str) example="23260.42ml"
  - `data.base.print_count` (int) example=77
  - `data.base.print_totaltime` (str) example="647??9?"
  - `data.device_status` (int) example=1
  - `data.external_shelves` (object)
  - `data.external_shelves.color` (list)
  - `data.external_shelves.color[]` (int) example=255
  - `data.external_shelves.id` (int) example=0
  - `data.external_shelves.type` (str) example="PLA"
  - `data.features` (null)
  - `data.free_temp_limit` (null)
  - `data.head_tools_model` (int) example=0
  - `data.help_url` (str) example=""
  - `data.id` (int) example=42859
  - `data.img` (str) example="https://cdn.cloud-platform.anycubic.com/php/img/4/m3plus.png"
  - `data.is_printing` (int) example=2
  - `data.is_read_quick_start_url` (int) example=0
  - `data.key` (str) example="35b1681ce52f58f18feffd6880a43d36"
  - `data.machine_data` (object)
  - `data.machine_data.anti_max` (int) example=8
  - `data.machine_data.format` (str) example="pw0Img"
  - `data.machine_data.name` (str) example="Photon M3 Plus"
  - `data.machine_data.pixel` (float) example=34.4
  - `data.machine_data.res_x` (int) example=5760
  - `data.machine_data.res_y` (int) example=3600
  - `data.machine_data.size_x` (int) example=197
  - `data.machine_data.size_y` (float) example=122.8
  - `data.machine_data.size_z` (int) example=245
  - `data.machine_data.suffix` (str) example="pwmb"
  - `data.machine_type` (int) example=107
  - `data.maintenance_manual_url` (str) example=""
  - `data.max_box_num` (int) example=0
  - `data.model` (str) example="Anycubic Photon M3 Plus"
  - `data.multi_color_box` (null)
  - `data.multi_color_box_version` (null)
  - `data.name` (str) example="Anycubic Photon M3 Plus"
  - `data.need_update` (int) example=0
  - `data.nozzle_diameter` (null)
  - `data.project` (object)
  - `data.project.compensation_layers` (str) example=""
  - `data.project.curr_layer` (int) example=155
  - `data.project.dual_platform_mode_enable` (int) example=0
  - `data.project.estimate` (int) example=11038
  - `data.project.estimate_supplies_usage` (float) example=4.621968746185303
  - `data.project.img` (str) example="https:....jpg"
  - `data.project.material_unit` (str) example="ml"
  - `data.project.name` (str) example="raven_skull_19_v3"
  - `data.project.on_time` (float) example=1.5
  - `data.project.pause` (int) example=0
  - `data.project.print_status` (int) example=1
  - `data.project.print_time` (int) example=38
  - `data.project.progress` (int) example=14
  - `data.project.project_type` (int) example=1
  - `data.project.reason_id` (int) example=0
  - `data.project.remain_time` (int) example=218
  - `data.project.slice_status` (int) example=0
  - `data.project.supplies_usage` (float) example=4.621969
  - `data.project.task_id` (int) example=72244987
  - `data.project.task_settings` (object)
  - `data.project.total_layers` (int) example=1073
  - `data.quick_start_url` (str) example=""
  - `data.releaseFilm` (object)
  - `data.releaseFilm.layers` (int) example=0
  - `data.releasefilm_url` (str) example=""
  - `data.rotate_deg` (int) example=0
  - `data.temp_limit` (null)
  - `data.tools` (list)
  - `data.tools[]` (empty)
  - `data.type_function_ids` (list)
  - `data.type_function_ids[]` (int) example=7
  - `data.version` (object)
  - `data.version.firmware_version` (str) example=""
  - `data.version.force_update` (int) example=0
  - `data.version.img` (str) example="https://cdn.cloud-platform.anycubic.com/php/img/4/m3plus.png"
  - `data.version.need_update` (int) example=0
  - `data.version.target_version` (str) example=""
  - `data.version.time_cost` (int) example=0
  - `data.version.update_date` (int) example=0
  - `data.version.update_desc` (str) example=""
  - `data.version.update_progress` (int) example=0
  - `data.version.update_status` (str) example=""
  - `msg` (str) example="????"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": {
    "advance": [],
    "base": {
      "create_time": 1708449350,
      "description": "A7F6-B0FF-F706-3D49",
      "firmware_version": null,
      "machine_mac": "6E-D0-8D-A8-5A-EE",
      "material_type": "??",
      "material_used": "23260.42ml",
      "print_count": 77,
      "print_totaltime": "647??9?"
    },
    "device_status": 1,
    "external_shelves": {
      "color": [
        255,
        255,
        255
      ],
      "id": 0,
      "type": "PLA"
    },
    "features": null,
    "free_temp_limit": null,
    "head_tools_model": 0,
    "help_url": "",
    "id": 42859,
    "img": "https://cdn.cloud-platform.anycubic.com/php/img/4/m3plus.png",
    "is_printing": 2,
    "is_read_quick_start_url": 0,
    "key": "35b1681ce52f58f18feffd6880a43d36",
    "machine_data": {
      "anti_max": 8,
      "format": "pw0Img",
      "name": "Photon M3 Plus",
      "pixel": 34.4,
      "res_x": 5760,
      "res_y": 3600,
      "size_x": 197,
      "size_y": 122.8,
      "size_z": 245,
      "suffix": "pwmb"
    },
    "machine_type": 107,
    "maintenance_manual_url": "",
    "max_box_num": 0,
    "model": "Anycubic Photon M3 Plus",
    "multi_color_box": null,
    "multi_color_box_version": null,
    "name": "Anycubic Photon M3 Plus",
    "need_update": 0,
    "nozzle_diameter": null,
    "project": {
      "compensation_layers": "",
      "curr_layer": 155,
      "dual_platform_mode_enable": 0,
      "estimate": 11038,
      "estimate_supplies_usage": 4.621968746185303,
      "img": "https:....jpg",
      "material_unit": "ml",
      "name": "raven_skull_19_v3",
      "on_time": 1.5,
      "pause": 0,
      "print_status": 1,
      "print_time": 38,
      "progress": 14,
      "project_type": 1,
      "reason_id": 0,
      "remain_time": 218,
      "slice_status": 0,
      "supplies_usage": 4.621969,
      "task_id": 72244987,
      "task_settings": {},
      "total_layers": 1073
    },
    "quick_start_url": "",
    "releaseFilm": {
      "layers": 0
    },
    "releasefilm_url": "",
    "rotate_deg": 0,
    "temp_limit": null,
    "tools": [],
    "type_function_ids": [
      7,
      22
    ],
    "version": {
      "firmware_version": "",
      "force_update": 0,
      "img": "https://cdn.cloud-platform.anycubic.com/php/img/4/m3plus.png",
      "need_update": 0,
      "target_version": "",
      "time_cost": 0,
      "update_date": 0,
      "update_desc": "",
      "update_progress": 0,
      "update_status": ""
    }
  },
  "msg": "????"
}
```

### `GET /p/p/workbench/api/v2/printer/printersStatus`
- Capture: oui (4 echantillon(s))
- Sources: log:cloud_Log.log.1 x4
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (list)
  - `data[]` (object)
  - `data[].available` (int) example=1
  - `data[].description` (str) example="A7F6-B0FF-F706-3D49"
  - `data[].device_status` (int) example=1
  - `data[].id` (int) example=42859
  - `data[].img` (str) example="https://cdn.cloud-platform.anycubic.com/php/img/4/m3plus.png"
  - `data[].is_printing` (int) example=1
  - `data[].key` (str) example="35b1681ce52f58f18feffd6880a43d36"
  - `data[].machine_type` (int) example=107
  - `data[].model` (str) example="Anycubic Photon M3 Plus"
  - `data[].name` (str) example="Anycubic Photon M3 Plus"
  - `data[].reason` (str) example="??"
  - `data[].type` (str) example="LCD"
  - `msg` (str) example="?????"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": [
    {
      "available": 1,
      "description": "A7F6-B0FF-F706-3D49",
      "device_status": 1,
      "id": 42859,
      "img": "https://cdn.cloud-platform.anycubic.com/php/img/4/m3plus.png",
      "is_printing": 1,
      "key": "35b1681ce52f58f18feffd6880a43d36",
      "machine_type": 107,
      "model": "Anycubic Photon M3 Plus",
      "name": "Anycubic Photon M3 Plus",
      "reason": "??",
      "type": "LCD"
    }
  ],
  "msg": "?????"
}
```

### `POST /p/p/workbench/api/v2/profile/newUploadFile`
- Capture: oui (5 echantillon(s))
- Sources: log:cloud_Log.log.1 x5
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (object)
  - `data.id` (int) example=50418549
  - `msg` (str) example="????"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": {
    "id": 50418549
  },
  "msg": "????"
}
```

### `GET /p/p/workbench/api/v2/project/info`
- Capture: oui (32 echantillon(s))
- Sources: log:cloud_Log.log x5, log:cloud_Log.log.1 x27
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (object)
  - `data.auto_operation` (null)
  - `data.create_time` (int) example=1770805803
  - `data.device_message` (object)
  - `data.device_message.action` (str) example="start"
  - `data.device_message.anti_count` (int) example=1
  - `data.device_message.curr_layer` (int) example=155
  - `data.device_message.err_message` (str) example=""
  - `data.device_message.filename` (str) example="raven_skull_19_v3.pwmb"
  - `data.device_message.heating_remain_time` (int) example=0
  - `data.device_message.model_hight` (float) example=53.650002
  - `data.device_message.print_time` (int) example=38
  - `data.device_message.progress` (int) example=14
  - `data.device_message.reason` (int) example=200
  - `data.device_message.remain_time` (int) example=218
  - `data.device_message.settings` (object)
  - `data.device_message.settings.bottom_layers` (int) example=4
  - `data.device_message.settings.bottom_time` (int) example=20
  - `data.device_message.settings.off_time` (int) example=1
  - `data.device_message.settings.on_time` (float) example=1.5
  - `data.device_message.settings.z_down_speed` (int) example=1
  - `data.device_message.settings.z_up_height` (int) example=3
  - `data.device_message.settings.z_up_speed` (int) example=1
  - `data.device_message.settings_adv` (object)
  - `data.device_message.settings_adv.trans_layers` (int) example=6
  - `data.device_message.settings_adv.z_down_speed_b0` (int) example=1
  - `data.device_message.settings_adv.z_down_speed_b1` (int) example=3
  - `data.device_message.settings_adv.z_down_speed_n0` (int) example=1
  - `data.device_message.settings_adv.z_down_speed_n1` (int) example=3
  - `data.device_message.settings_adv.z_up_height_b0` (int) example=3
  - `data.device_message.settings_adv.z_up_height_b1` (int) example=4
  - `data.device_message.settings_adv.z_up_height_n0` (int) example=3
  - `data.device_message.settings_adv.z_up_height_n1` (int) example=4
  - `data.device_message.settings_adv.z_up_speed_b0` (int) example=1
  - `data.device_message.settings_adv.z_up_speed_b1` (int) example=3
  - `data.device_message.settings_adv.z_up_speed_n0` (int) example=1
  - `data.device_message.settings_adv.z_up_speed_n1` (int) example=3
  - `data.device_message.state` (str) example="printing"
  - `data.device_message.supplies_usage` (float) example=4.621969
  - `data.device_message.task_mode` (int) example=1
  - `data.device_message.taskid` (str) example="72244987"
  - `data.device_message.timestamp` (int) example=1770808141169
  - `data.device_message.total_layers` (int) example=1073
  - `data.device_message.z_thick` (float) example=0.05
  - `data.end_time` (int) example=0
  - `data.gcode_id` (int) example=71469071
  - `data.gcode_name` (str) example="raven_skull_19_v3"
  - `data.id` (int) example=72244987
  - `data.img` (str) example="https:....jpg"
  - `data.is_feedback` (int) example=0
  - `data.key` (str) example="35b1681ce52f58f18feffd6880a43d36"
  - `data.machine_name` (str) example="Anycubic Photon M3 Plus"
  - `data.machine_type` (int) example=107
  - `data.material` (str) example="4.6219687461853"
  - `data.material_unit` (str) example="ml"
  - `data.model` (str) example="Anycubic Photon M3 Plus"
  - `data.monitor` (null)
  - `data.pause` (int) example=0
  - `data.post_id` (int) example=0
  - `data.post_title` (null)
  - `data.print_status` (int) example=1
  - `data.printer_monitor` (int) example=0
  - `data.printer_name` (str) example="Anycubic Photon M3 Plus"
  - `data.printer_type` (str) example="LCD"
  - `data.progress` (int) example=14
  - `data.project_type` (int) example=1
  - `data.reason` (str) example="0"
  - `data.reason_help_url` (null)
  - `data.reason_id` (int) example=0
  - `data.rotate_deg` (int) example=0
  - `data.set_limit` (object)
  - `data.set_limit.auto_support` (object)
  - `data.set_limit.auto_support.angle` (list)
  - `data.set_limit.auto_support.angle[]` (int) example=0
  - `data.set_limit.auto_support.density` (list)
  - `data.set_limit.auto_support.density[]` (int) example=0
  - `data.set_limit.auto_support.lift_height` (list)
  - `data.set_limit.auto_support.lift_height[]` (float) example=0.0
  - `data.set_limit.auto_support.min_length` (list)
  - `data.set_limit.auto_support.min_length[]` (int) example=0
  - `data.set_limit.bott_layers` (list)
  - `data.set_limit.bott_layers[]` (int) example=1
  - `data.set_limit.bott_time` (list)
  - `data.set_limit.bott_time[]` (float) example=0.1
  - `data.set_limit.exposure_time` (list)
  - `data.set_limit.exposure_time[]` (float) example=0.1
  - `data.set_limit.off_time` (list)
  - `data.set_limit.off_time[]` (float) example=0.1
  - `data.set_limit.zdown_speed` (list)
  - `data.set_limit.zdown_speed[]` (float) example=0.1
  - `data.set_limit.zthick` (list)
  - `data.set_limit.zthick[]` (float) example=0.01
  - `data.set_limit.zup_height` (list)
  - `data.set_limit.zup_height[]` (float) example=0.1
  - `data.set_limit.zup_speed` (list)
  - `data.set_limit.zup_speed[]` (float) example=0.1
  - `data.slice_param` (object)
  - `data.slice_param.bott_layers` (int) example=4
  - `data.slice_param.bott_time` (float) example=20.0
  - `data.slice_param.exposure_time` (float) example=1.5
  - `data.slice_param.material_name` (str) example="\u6811\u8102"
  - `data.slice_param.off_time` (float) example=1.0
  - `data.slice_param.zdown_speed` (float) example=1.0
  - `data.slice_param.zthick` (float) example=0.05000000074505806
  - `data.slice_param.zup_height` (float) example=3.0
  - `data.slice_param.zup_speed` (float) example=1.0
  - `data.slice_result` (object)
  - `data.slice_result.size_x` (float) example=0.0
  - `data.slice_result.size_y` (float) example=0.0
  - `data.slice_result.size_z` (float) example=53.650001525878906
  - `data.slice_status` (int) example=0
  - `data.sliced_plates` (null)
  - `data.task_mode` (int) example=1
  - `data.task_settings` (object)
  - `data.total_time` (str) example="0"
  - `data.type_function_ids` (list)
  - `data.type_function_ids[]` (int) example=7
  - `data.z_thick` (float) example=0.05
  - `msg` (str) example="\u8fde\u63a5\u6210\u529f"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": {
    "auto_operation": null,
    "create_time": 1770805803,
    "device_message": {
      "action": "start",
      "anti_count": 1,
      "curr_layer": 155,
      "err_message": "",
      "filename": "raven_skull_19_v3.pwmb",
      "heating_remain_time": 0,
      "model_hight": 53.650002,
      "print_time": 38,
      "progress": 14,
      "reason": 200,
      "remain_time": 218,
      "settings": {
        "bottom_layers": 4,
        "bottom_time": 20,
        "off_time": 1,
        "on_time": 1.5,
        "z_down_speed": 1,
        "z_up_height": 3,
        "z_up_speed": 1
      },
      "settings_adv": {
        "trans_layers": 6,
        "z_down_speed_b0": 1,
        "z_down_speed_b1": 3,
        "z_down_speed_n0": 1,
        "z_down_speed_n1": 3,
        "z_up_height_b0": 3,
        "z_up_height_b1": 4,
        "z_up_height_n0": 3,
        "z_up_height_n1": 4,
        "z_up_speed_b0": 1,
        "z_up_speed_b1": 3,
        "z_up_speed_n0": 1,
        "z_up_speed_n1": 3
      },
      "state": "printing",
      "supplies_usage": 4.621969,
      "task_mode": 1,
      "taskid": "72244987",
      "timestamp": 1770808141169,
      "total_layers": 1073,
      "z_thick": 0.05
    },
    "end_time": 0,
    "gcode_id": 71469071,
    "gcode_name": "raven_skull_19_v3",
    "id": 72244987,
    "img": "https:....jpg",
    "is_feedback": 0,
    "key": "35b1681ce52f58f18feffd6880a43d36",
    "machine_name": "Anycubic Photon M3 Plus",
    "machine_type": 107,
    "material": "4.6219687461853",
    "material_unit": "ml",
    "model": "Anycubic Photon M3 Plus",
    "monitor": null,
    "pause": 0,
    "post_id": 0,
    "post_title": null,
    "print_status": 1,
    "printer_monitor": 0,
    "printer_name": "Anycubic Photon M3 Plus",
    "printer_type": "LCD",
    "progress": 14,
    "project_type": 1,
    "reason": "0",
    "reason_help_url": null,
    "reason_id": 0,
    "rotate_deg": 0,
    "set_limit": {
      "auto_support": {
        "angle": [
          0,
          80
        ],
        "density": [
          0,
          99
        ],
        "lift_height": [
          0.0,
          1000.0
        ],
        "min_length": [
          0,
          20
        ]
      },
      "bott_layers": [
        1,
        200
      ],
      "bott_time": [
        0.1,
        200
      ],
      "exposure_time": [
        0.1,
        200
      ],
      "off_time": [
        0.1,
        200
      ],
      "zdown_speed": [
        0.1,
        20
      ],
      "zthick": [
        0.01,
        0.3
      ],
      "zup_height": [
        0.1,
        50
      ],
      "zup_speed": [
        0.1,
        20
      ]
    },
    "slice_param": {
      "bott_layers": 4,
      "bott_time": 20.0,
      "exposure_time": 1.5,
      "material_name": "\u6811\u8102",
      "off_time": 1.0,
      "zdown_speed": 1.0,
      "zthick": 0.05000000074505806,
      "zup_height": 3.0,
      "zup_speed": 1.0
    },
    "slice_result": {
      "size_x": 0.0,
      "size_y": 0.0,
      "size_z": 53.650001525878906
    },
    "slice_status": 0,
    "sliced_plates": null,
    "task_mode": 1,
    "task_settings": {},
    "total_time": "0",
    "type_function_ids": [
      7,
      22
    ],
    "z_thick": 0.05
  },
  "msg": "\u8fde\u63a5\u6210\u529f"
}
```

### `GET /p/p/workbench/api/v3/public/getoauthToken`
- Capture: oui (1 echantillon(s))
- Sources: har:uc.makeronline.com.har x1
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (object)
  - `data.access_token` (str) example="eyJhbG...iWhU"
  - `data.expires` (int) example=1779493986
  - `data.id_token` (str) example="eyJhbG...iWhU"
  - `data.refresh_token` (str) example="eyJhbG...92MI"
  - `data.scope` (str) example="read"
  - `data.token_type` (str) example="<masked>"
  - `msg` (str) example="\u64cd\u4f5c\u6210\u529f"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": {
    "access_token": "eyJhbG...iWhU",
    "expires": 1779493986,
    "id_token": "eyJhbG...iWhU",
    "refresh_token": "eyJhbG...92MI",
    "scope": "read",
    "token_type": "<masked>"
  },
  "msg": "\u64cd\u4f5c\u6210\u529f"
}
```

### `POST /p/p/workbench/api/v3/public/loginWithAccessToken`
- Capture: oui (4 echantillon(s))
- Sources: har:uc.makeronline.com.har x1, log:cloud_Log.log.1 x3
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (object)
  - `data.login_status` (int) example=1
  - `data.token` (str) example="eyJ0eX...8u2w"
  - `data.user` (object)
  - `data.user.apply_designer_status` (int) example=0
  - `data.user.avatar` (str) example="https:....png"
  - `data.user.avatar_store_type` (int) example=0
  - `data.user.balance` (str) example="0.00"
  - `data.user.birthday` (str) example="1970-01-01"
  - `data.user.casdoor_user` (object)
  - `data.user.casdoor_user.avatar` (str) example="https:....png"
  - `data.user.casdoor_user.birthday` (str) example=""
  - `data.user.casdoor_user.control_reason` (str) example=""
  - `data.user.casdoor_user.control_reason_map` (str) example=""
  - `data.user.casdoor_user.country_code` (str) example=""
  - `data.user.casdoor_user.created_time` (str) example="2024-02-19T20:49:45+08:00"
  - `data.user.casdoor_user.display_country_code` (str) example=""
  - `data.user.casdoor_user.display_name` (str) example="Molgo"
  - `data.user.casdoor_user.email` (str) example="d***d@zelisko.fr"
  - `data.user.casdoor_user.forbid_contest` (int) example=0
  - `data.user.casdoor_user.forbid_giving_gift` (int) example=0
  - `data.user.casdoor_user.forbid_model` (int) example=0
  - `data.user.casdoor_user.forbid_points` (int) example=0
  - `data.user.casdoor_user.forbid_points_consume` (int) example=0
  - `data.user.casdoor_user.forbid_post` (int) example=0
  - `data.user.casdoor_user.forbid_post_comment` (int) example=0
  - `data.user.casdoor_user.forbid_printfile` (int) example=0
  - `data.user.casdoor_user.forbid_publish_wish` (int) example=0
  - `data.user.casdoor_user.freeze_created_at` (str) example=""
  - `data.user.casdoor_user.freeze_cycle` (int) example=0
  - `data.user.casdoor_user.freeze_login` (int) example=0
  - `data.user.casdoor_user.freeze_remark` (str) example=""
  - `data.user.casdoor_user.gender` (str) example="1"
  - `data.user.casdoor_user.id` (str) example="e1bf0028-e708-4117-b18c-b692e6937e5a"
  - `data.user.casdoor_user.identity_id` (str) example="4106224"
  - `data.user.casdoor_user.integral` (int) example=1
  - `data.user.casdoor_user.introduction` (str) example=""
  - `data.user.casdoor_user.is_deleted` (int) example=0
  - `data.user.casdoor_user.is_freeze` (int) example=0
  - `data.user.casdoor_user.is_user_risk` (int) example=0
  - `data.user.casdoor_user.is_user_risk_user_white` (int) example=0
  - `data.user.casdoor_user.is_verify` (int) example=0
  - `data.user.casdoor_user.mirror_forbid_sync_points` (int) example=0
  - `data.user.casdoor_user.mold_is_demotion` (int) example=0
  - `data.user.casdoor_user.mold_is_review` (int) example=0
  - `data.user.casdoor_user.mold_publish_set_c` (int) example=0
  - `data.user.casdoor_user.owner` (str) example="anycubic"
  - `data.user.casdoor_user.phone` (str) example=""
  - `data.user.casdoor_user.print_type` (int) example=0
  - `data.user.casdoor_user.printer_id` (int) example=0
  - `data.user.casdoor_user.printfile_is_review` (int) example=0
  - `data.user.casdoor_user.revenue_coin` (int) example=0
  - `data.user.casdoor_user.signup_application` (str) example="ac_android"
  - `data.user.casdoor_user.signup_port` (str) example="Mobile"
  - `data.user.casdoor_user.signup_type` (str) example="email"
  - `data.user.casdoor_user.social_links` (null)
  - `data.user.casdoor_user.tag_at` (null)
  - `data.user.casdoor_user.token_coin` (int) example=0
  - `data.user.casdoor_user.unfreeze_time` (str) example=""
  - `data.user.casdoor_user.updated_time` (str) example="2025-03-13T20:22:15+08:00"
  - `data.user.casdoor_user.user_name` (str) example="Molgo"
  - `data.user.casdoor_user.user_remarks` (null)
  - `data.user.casdoor_user.user_risk_user_white` (null)
  - `data.user.casdoor_user.user_tag` (null)
  - `data.user.casdoor_user_id` (str) example="e1bf0028-e708-4117-b18c-b692e6937e5a"
  - `data.user.city` (int) example=0
  - `data.user.coin` (int) example=0
  - `data.user.country` (int) example=0
  - `data.user.create_day_time` (int) example=1708358400
  - `data.user.create_time` (int) example=1708375785
  - `data.user.id` (int) example=94829
  - `data.user.ip_city` (str) example="0"
  - `data.user.ip_country` (str) example="??"
  - `data.user.ip_province` (str) example="0"
  - `data.user.is_inner` (int) example=0
  - `data.user.label` (list)
  - `data.user.label[]` (empty)
  - `data.user.last_login_ip` (str) example="82.64.136.10"
  - `data.user.last_login_time` (int) example=1770307171
  - `data.user.last_print_time` (int) example=0
  - `data.user.login_type` (int) example=0
  - `data.user.message_key` (str) example=""
  - `data.user.mobile` (str) example=""
  - `data.user.mobile_country_code` (str) example="0"
  - `data.user.mobile_country_id` (int) example=0
  - `data.user.more` (list)
  - `data.user.more[]` (empty)
  - `data.user.new_message` (int) example=69
  - `data.user.professional` (str) example=""
  - `data.user.province` (int) example=0
  - `data.user.register_source` (int) example=1
  - `data.user.register_type` (int) example=1
  - `data.user.score` (int) example=0
  - `data.user.sex` (int) example=1
  - `data.user.signature` (str) example=""
  - `data.user.task_count` (int) example=1
  - `data.user.total` (object)
  - `data.user.total.favorite` (int) example=0
  - `data.user.total.like` (int) example=0
  - `data.user.total.post_count` (int) example=0
  - `data.user.tourist_device_id` (str) example="unkonw"
  - `data.user.type` (str) example="1"
  - `data.user.uploadsize_status` (object)
  - `data.user.uploadsize_status.total` (str) example="2048M"
  - `data.user.uploadsize_status.total_bytes` (int) example=2147483648
  - `data.user.uploadsize_status.used` (str) example="1161M"
  - `data.user.uploadsize_status.used_bytes` (int) example=1218090634
  - `data.user.user_activation_key` (str) example=""
  - `data.user.user_email` (str) example="d***d@zelisko.fr"
  - `data.user.user_login` (str) example=""
  - `data.user.user_nickname` (str) example="Molgo"
  - `data.user.user_pass` (str) example=""
  - `data.user.user_status` (int) example=1
  - `data.user.user_type` (int) example=2
  - `data.user.user_url` (str) example=""
  - `msg` (str) example="????"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": {
    "login_status": 1,
    "token": "eyJ0eX...8u2w",
    "user": {
      "apply_designer_status": 0,
      "avatar": "https:....png",
      "avatar_store_type": 0,
      "balance": "0.00",
      "birthday": "1970-01-01",
      "casdoor_user": {
        "avatar": "https:....png",
        "birthday": "",
        "control_reason": "",
        "control_reason_map": "",
        "country_code": "",
        "created_time": "2024-02-19T20:49:45+08:00",
        "display_country_code": "",
        "display_name": "Molgo",
        "email": "d***d@zelisko.fr",
        "forbid_contest": 0,
        "forbid_giving_gift": 0,
        "forbid_model": 0,
        "forbid_points": 0,
        "forbid_points_consume": 0,
        "forbid_post": 0,
        "forbid_post_comment": 0,
        "forbid_printfile": 0,
        "forbid_publish_wish": 0,
        "freeze_created_at": "",
        "freeze_cycle": 0,
        "freeze_login": 0,
        "freeze_remark": "",
        "gender": "1",
        "id": "e1bf0028-e708-4117-b18c-b692e6937e5a",
        "identity_id": "4106224",
        "integral": 1,
        "introduction": "",
        "is_deleted": 0,
        "is_freeze": 0,
        "is_user_risk": 0,
        "is_user_risk_user_white": 0,
        "is_verify": 0,
        "mirror_forbid_sync_points": 0,
        "mold_is_demotion": 0,
        "mold_is_review": 0,
        "mold_publish_set_c": 0,
        "owner": "anycubic",
        "phone": "",
        "print_type": 0,
        "printer_id": 0,
        "printfile_is_review": 0,
        "revenue_coin": 0,
        "signup_application": "ac_android",
        "signup_port": "Mobile",
        "signup_type": "email",
        "social_links": null,
        "tag_at": null,
        "token_coin": 0,
        "unfreeze_time": "",
        "updated_time": "2025-03-13T20:22:15+08:00",
        "user_name": "Molgo",
        "user_remarks": null,
        "user_risk_user_white": null,
        "user_tag": null
      },
      "casdoor_user_id": "e1bf0028-e708-4117-b18c-b692e6937e5a",
      "city": 0,
      "coin": 0,
      "country": 0,
      "create_day_time": 1708358400,
      "create_time": 1708375785,
      "id": 94829,
      "ip_city": "0",
      "ip_country": "??",
      "ip_province": "0",
      "is_inner": 0,
      "label": [],
      "last_login_ip": "82.64.136.10",
      "last_login_time": 1770307171,
      "last_print_time": 0,
      "login_type": 0,
      "message_key": "",
      "mobile": "",
      "mobile_country_code": "0",
      "mobile_country_id": 0,
      "more": [],
      "new_message": 69,
      "professional": "",
      "province": 0,
      "register_source": 1,
      "register_type": 1,
      "score": 0,
      "sex": 1,
      "signature": "",
      "task_count": 1,
      "total": {
        "favorite": 0,
        "like": 0,
        "post_count": 0
      },
      "tourist_device_id": "unkonw",
      "type": "1",
      "uploadsize_status": {
        "total": "2048M",
        "total_bytes": 2147483648,
        "used": "1161M",
        "used_bytes": 1218090634
      },
      "user_activation_key": "",
      "user_email": "d***d@zelisko.fr",
      "user_login": "",
      "user_nickname": "Molgo",
      "user_pass": "",
      "user_status": 1,
      "user_type": 2,
      "user_url": ""
    }
  },
  "msg": "????"
}
```

### `POST /p/p/workbench/api/work/index/delFiles`
- Capture: non
- Modele JSON attendu (source `api_map.json`):
```json
{
  "code": 1,
  "data": ""
}
```

### `POST /p/p/workbench/api/work/index/files`
- Capture: oui (2 echantillon(s))
- Sources: har:uc.makeronline.com.har x2
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (list)
  - `data[]` (object)
  - `data[].bucket` (str) example="workbentch"
  - `data[].desc` (str) example=""
  - `data[].device_type` (str) example="web"
  - `data[].estimate` (int) example=1052
  - `data[].file_extension` (str) example="pwmb"
  - `data[].file_source` (int) example=1
  - `data[].file_type` (int) example=1
  - `data[].filename` (str) example="177166666698895100-fb91807c62b2b6318ae2d0ce60249ab6-69997ceaf1722bbb38e6199700e205c5.pwmb"
  - `data[].gcode_id` (int) example=73620739
  - `data[].id` (int) example=53095239
  - `data[].img_status` (int) example=1
  - `data[].ip` (str) example="82.64.136.10"
  - `data[].is_delete` (int) example=0
  - `data[].is_official_slice` (int) example=0
  - `data[].is_parse` (int) example=1
  - `data[].is_temp_file` (int) example=0
  - `data[].layer_height` (float) example=0.05000000074505806
  - `data[].machine_type` (int) example=0
  - `data[].material_name` (str) example="Resin"
  - `data[].md5` (str) example="8162e4418287008333b3441e519bb8cb"
  - `data[].name_counts` (int) example=0
  - `data[].official_file_id` (int) example=0
  - `data[].official_file_key` (str) example=""
  - `data[].official_file_type` (int) example=-1
  - `data[].old_filename` (str) example="cube2.pwmb"
  - `data[].origin_file_md5` (str) example="8162e4418287008333b3441e519bb8cb"
  - `data[].origin_post_id` (int) example=0
  - `data[].path` (str) example="file/2026/02/21/pwmb/177166666698895100-fb91807c62b2b6318ae2d0ce60249ab6-69997ceaf1722bbb38e6199700e205c5.pwmb"
  - `data[].plate_number` (int) example=0
  - `data[].post_id` (int) example=0
  - `data[].printer_image_id` (str) example=""
  - `data[].printer_names` (list)
  - `data[].printer_names[]` (str) example="Photon Mono M3 Plus"
  - `data[].region` (str) example="us-east-2"
  - `data[].simplify_model` (list)
  - `data[].simplify_model[]` (empty)
  - `data[].size` (int) example=2304920
  - `data[].size_x` (int) example=0
  - `data[].size_y` (int) example=0
  - `data[].size_z` (float|int) example=10
  - `data[].slice_param` (object)
  - `data[].slice_param.advanced_control` (object)
  - `data[].slice_param.advanced_control.bott_0` (object)
  - `data[].slice_param.advanced_control.bott_0.down_speed` (int) example=1
  - `data[].slice_param.advanced_control.bott_0.height` (int) example=3
  - `data[].slice_param.advanced_control.bott_0.z_up_speed` (int) example=1
  - `data[].slice_param.advanced_control.bott_1` (object)
  - `data[].slice_param.advanced_control.bott_1.down_speed` (int) example=3
  - `data[].slice_param.advanced_control.bott_1.height` (int) example=4
  - `data[].slice_param.advanced_control.bott_1.up_speed` (int) example=3
  - `data[].slice_param.advanced_control.multi_state_used` (int) example=1
  - `data[].slice_param.advanced_control.normal_0` (object)
  - `data[].slice_param.advanced_control.normal_0.down_speed` (int) example=3
  - `data[].slice_param.advanced_control.normal_0.height` (int) example=3
  - `data[].slice_param.advanced_control.normal_0.up_speed` (int) example=3
  - `data[].slice_param.advanced_control.normal_1` (object)
  - `data[].slice_param.advanced_control.normal_1.down_speed` (int) example=6
  - `data[].slice_param.advanced_control.normal_1.height` (int) example=3
  - `data[].slice_param.advanced_control.normal_1.up_speed` (int) example=6
  - `data[].slice_param.advanced_control.transition_layercount` (int) example=6
  - `data[].slice_param.anti_count` (int) example=8
  - `data[].slice_param.basic_control_param` (object)
  - `data[].slice_param.basic_control_param.zdown_speed` (int) example=3
  - `data[].slice_param.basic_control_param.zup_height` (int) example=3
  - `data[].slice_param.basic_control_param.zup_speed` (int) example=3
  - `data[].slice_param.bott_layers` (int) example=4
  - `data[].slice_param.bott_time` (int) example=20
  - `data[].slice_param.bucket_id` (str) example="cloud-slice-prod"
  - `data[].slice_param.estimate` (int) example=1052
  - `data[].slice_param.exposure_time` (float) example=1.5
  - `data[].slice_param.image_id` (str) example="cloud/2026-02/21/jpg/d568f8224715497fb449d2ae622d4ae0.jpg"
  - `data[].slice_param.intelli_mode` (int) example=0
  - `data[].slice_param.layers` (int) example=200
  - `data[].slice_param.machine_name` (str) example="Photon Mono M3 Plus"
  - `data[].slice_param.machine_param` (object)
  - `data[].slice_param.machine_param.name` (str) example="Photon Mono M3 Plus"
  - `data[].slice_param.machine_tid` (int) example=0
  - `data[].slice_param.material_name` (str) example="Basic"
  - `data[].slice_param.material_tid` (int) example=0
  - `data[].slice_param.off_time` (float) example=0.5
  - `data[].slice_param.size_x` (int) example=0
  - `data[].slice_param.size_y` (int) example=0
  - `data[].slice_param.size_z` (float|int) example=10
  - `data[].slice_param.sliced_md5` (str) example="8162e4418287008333b3441e519bb8cb"
  - `data[].slice_param.supplies_usage` (float) example=0.9952057600021362
  - `data[].slice_param.zdown_speed` (int) example=3
  - `data[].slice_param.zthick` (float) example=0.05000000074505806
  - `data[].slice_param.zup_height` (int) example=3
  - `data[].slice_param.zup_speed` (int) example=3
  - `data[].sliceparse_nonce` (str) example="69997c...126d"
  - `data[].source_type` (int) example=0
  - `data[].source_user_upload_id` (int) example=0
  - `data[].status` (int) example=1
  - `data[].stl_user_upload_id` (int) example=0
  - `data[].store_type` (int) example=2
  - `data[].supplies_usage` (float) example=0.9952057600021362
  - `data[].thumbnail` (str) example="https:....jpg"
  - `data[].thumbnail_nonce` (str) example=""
  - `data[].time` (int) example=1771666668
  - `data[].triangles_count` (int) example=0
  - `data[].update_time` (int) example=1771666668
  - `data[].url` (str) example="https:...pwmb"
  - `data[].user_id` (int) example=94829
  - `data[].user_lock_space_id` (int) example=43732742
  - `data[].uuid` (str) example=""
  - `msg` (str) example="\u8bf7\u6c42\u88ab\u63a5\u53d7"
  - `pageData` (object)
  - `pageData.page` (int) example=1
  - `pageData.page_count` (int) example=10
  - `pageData.total` (int) example=20
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": [
    {
      "bucket": "workbentch",
      "desc": "",
      "device_type": "pc",
      "estimate": 4698,
      "file_extension": "pwmb",
      "file_source": 6,
      "file_type": 1,
      "filename": "175899076386712700-87a91f99fe5d4a65b6fde22f3be44d18-68d811abd3b424614c7a64fcba1d7f78.pwmb",
      "gcode_id": 44711101,
      "id": 30848305,
      "img_status": 0,
      "ip": "82.64.136.10",
      "is_delete": 0,
      "is_official_slice": 0,
      "is_parse": 1,
      "is_temp_file": 0,
      "layer_height": 0.05000000074505806,
      "machine_type": 107,
      "material_name": "Resin",
      "md5": "1d3aff6dfda0ffd0438eceda7eb817a0",
      "name_counts": 0,
      "official_file_id": 0,
      "official_file_key": "",
      "official_file_type": -1,
      "old_filename": "skull_cut_25_15_v3.pwmb",
      "origin_file_md5": "1d3aff6dfda0ffd0438eceda7eb817a0",
      "origin_post_id": 0,
      "path": "file/2025/09/28/pwmb/175899076386712700-87a91f99fe5d4a65b6fde22f3be44d18-68d811abd3b424614c7a64fcba1d7f78.pwmb",
      "plate_number": 0,
      "post_id": 0,
      "printer_image_id": "",
      "printer_names": [
        "Anycubic Photon M3 Plus"
      ],
      "region": "us-east-2",
      "simplify_model": [],
      "size": 59654301,
      "size_x": 0,
      "size_y": 0,
      "size_z": 23.5,
      "slice_param": {
        "advanced_control": {
          "bott_0": {
            "down_speed": 1,
            "height": 3,
            "z_up_speed": 1
          },
          "bott_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "multi_state_used": 0,
          "normal_0": {
            "down_speed": 1,
            "height": 3,
            "up_speed": 1
          },
          "normal_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "transition_layercount": 10
        },
        "anti_count": 16,
        "basic_control_param": {
          "zdown_speed": 6,
          "zup_height": 6,
          "zup_speed": 6
        },
        "bott_layers": 6,
        "bott_time": 23,
        "bucket_id": "cloud-slice-prod",
        "estimate": 4698,
        "exposure_time": 1.5,
        "image_id": "cloud/2025-09/27/jpg/1f8d69a796453be6875bee21b264cf9e.jpg",
        "intelli_mode": 0,
        "layers": 470,
        "machine_name": "Anycubic Photon M3 Plus",
        "machine_param": {
          "name": "Anycubic Photon M3 Plus"
        },
        "machine_tid": 0,
        "material_name": "Basic",
        "material_tid": 0,
        "off_time": 0.5,
        "size_x": 0,
        "size_y": 0,
        "size_z": 23.5,
        "sliced_md5": "1d3aff6dfda0ffd0438eceda7eb817a0",
        "supplies_usage": 68.18040466308594,
        "zdown_speed": 6,
        "zthick": 0.05000000074505806,
        "zup_height": 6,
        "zup_speed": 6
      },
      "sliceparse_nonce": "68d811...ec91",
      "source_type": 0,
      "source_user_upload_id": 0,
      "status": 1,
      "stl_user_upload_id": 0,
      "store_type": 2,
      "supplies_usage": 68.18040466308594,
      "thumbnail": "https:....jpg",
      "thumbnail_nonce": "",
      "time": 1758990771,
      "triangles_count": 0,
      "update_time": 1758990772,
      "url": "https:...pwmb",
      "user_id": 94829,
      "user_lock_space_id": 25257665,
      "uuid": ""
    },
    {
      "bucket": "workbentch",
      "desc": "",
      "device_type": "pc",
      "estimate": 4698,
      "file_extension": "pwmb",
      "file_source": 6,
      "file_type": 1,
      "filename": "175887385215225700-347328c5a0bc6aa84edf2c7686020490-68d648fc252ccd4ba742843c3eb82ae3.pwmb",
      "gcode_id": 44500408,
      "id": 30693546,
      "img_status": 0,
      "ip": "82.64.136.10",
      "is_delete": 0,
      "is_official_slice": 0,
      "is_parse": 1,
      "is_temp_file": 0,
      "layer_height": 0.05000000074505806,
      "machine_type": 107,
      "material_name": "Resin",
      "md5": "191775f043ca0c5e77762ad3f57a313d",
      "name_counts": 0,
      "official_file_id": 0,
      "official_file_key": "",
      "official_file_type": -1,
      "old_filename": "skull_cut_25_20_v3.pwmb",
      "origin_file_md5": "191775f043ca0c5e77762ad3f57a313d",
      "origin_post_id": 0,
      "path": "file/2025/09/26/pwmb/175887385215225700-347328c5a0bc6aa84edf2c7686020490-68d648fc252ccd4ba742843c3eb82ae3.pwmb",
      "plate_number": 0,
      "post_id": 0,
      "printer_image_id": "",
      "printer_names": [
        "Anycubic Photon M3 Plus"
      ],
      "region": "us-east-2",
      "simplify_model": [],
      "size": 77933333,
      "size_x": 0,
      "size_y": 0,
      "size_z": 23.5,
      "slice_param": {
        "advanced_control": {
          "bott_0": {
            "down_speed": 1,
            "height": 3,
            "z_up_speed": 1
          },
          "bott_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "multi_state_used": 0,
          "normal_0": {
            "down_speed": 1,
            "height": 3,
            "up_speed": 1
          },
          "normal_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "transition_layercount": 10
        },
        "anti_count": 16,
        "basic_control_param": {
          "zdown_speed": 6,
          "zup_height": 6,
          "zup_speed": 6
        },
        "bott_layers": 6,
        "bott_time": 23,
        "bucket_id": "cloud-slice-prod",
        "estimate": 4698,
        "exposure_time": 1.5,
        "image_id": "cloud/2025-09/26/jpg/204d5657d0915567de05d83a21ff73de.jpg",
        "intelli_mode": 0,
        "layers": 470,
        "machine_name": "Anycubic Photon M3 Plus",
        "machine_param": {
          "name": "Anycubic Photon M3 Plus"
        },
        "machine_tid": 0,
        "material_name": "Basic",
        "material_tid": 0,
        "off_time": 0.5,
        "size_x": 0,
        "size_y": 0,
        "size_z": 23.5,
        "sliced_md5": "191775f043ca0c5e77762ad3f57a313d",
        "supplies_usage": 90.91744232177734,
        "zdown_speed": 6,
        "zthick": 0.05000000074505806,
        "zup_height": 6,
        "zup_speed": 6
      },
      "sliceparse_nonce": "68d649...e1d8",
      "source_type": 0,
      "source_user_upload_id": 0,
      "status": 1,
      "stl_user_upload_id": 0,
      "store_type": 2,
      "supplies_usage": 90.91744232177734,
      "thumbnail": "https:....jpg",
      "thumbnail_nonce": "",
      "time": 1758873860,
      "triangles_count": 0,
      "update_time": 1758873861,
      "url": "https:...pwmb",
      "user_id": 94829,
      "user_lock_space_id": 25123497,
      "uuid": ""
    },
    {
      "bucket": "workbentch",
      "desc": "",
      "device_type": "pc",
      "estimate": 3927,
      "file_extension": "pwmb",
      "file_source": 6,
      "file_type": 1,
      "filename": "175887313724953300-7c27dbe11bccff18d2229c2cd241829d-68d646313cec86bcd6937b1459c64332.pwmb",
      "gcode_id": 44499392,
      "id": 30692855,
      "img_status": 0,
      "ip": "82.64.136.10",
      "is_delete": 0,
      "is_official_slice": 0,
      "is_parse": 1,
      "is_temp_file": 0,
      "layer_height": 0.05000000074505806,
      "machine_type": 107,
      "material_name": "Resin",
      "md5": "3652d651816e47d0b44eac6208d3f504",
      "name_counts": 0,
      "official_file_id": 0,
      "official_file_key": "",
      "official_file_type": -1,
      "old_filename": "skull_cut_19_15_v3.pwmb",
      "origin_file_md5": "3652d651816e47d0b44eac6208d3f504",
      "origin_post_id": 0,
      "path": "file/2025/09/26/pwmb/175887313724953300-7c27dbe11bccff18d2229c2cd241829d-68d646313cec86bcd6937b1459c64332.pwmb",
      "plate_number": 0,
      "post_id": 0,
      "printer_image_id": "",
      "printer_names": [
        "Anycubic Photon M3 Plus"
      ],
      "region": "us-east-2",
      "simplify_model": [],
      "size": 29285208,
      "size_x": 0,
      "size_y": 0,
      "size_z": 19.05000114440918,
      "slice_param": {
        "advanced_control": {
          "bott_0": {
            "down_speed": 1,
            "height": 3,
            "z_up_speed": 1
          },
          "bott_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "multi_state_used": 0,
          "normal_0": {
            "down_speed": 1,
            "height": 3,
            "up_speed": 1
          },
          "normal_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "transition_layercount": 10
        },
        "anti_count": 16,
        "basic_control_param": {
          "zdown_speed": 6,
          "zup_height": 6,
          "zup_speed": 6
        },
        "bott_layers": 6,
        "bott_time": 23,
        "bucket_id": "cloud-slice-prod",
        "estimate": 3927,
        "exposure_time": 1.5,
        "image_id": "cloud/2025-09/26/jpg/2a363f97d360050018c1b5b2ec2e6ae7.jpg",
        "intelli_mode": 0,
        "layers": 381,
        "machine_name": "Anycubic Photon M3 Plus",
        "machine_param": {
          "name": "Anycubic Photon M3 Plus"
        },
        "machine_tid": 0,
        "material_name": "Basic",
        "material_tid": 0,
        "off_time": 0.5,
        "size_x": 0,
        "size_y": 0,
        "size_z": 19.05000114440918,
        "sliced_md5": "3652d651816e47d0b44eac6208d3f504",
        "supplies_usage": 30.878904342651367,
        "zdown_speed": 6,
        "zthick": 0.05000000074505806,
        "zup_height": 6,
        "zup_speed": 6
      },
      "sliceparse_nonce": "68d646...2675",
      "source_type": 0,
      "source_user_upload_id": 0,
      "status": 1,
      "stl_user_upload_id": 0,
      "store_type": 2,
      "supplies_usage": 30.878904342651367,
      "thumbnail": "https:....jpg",
      "thumbnail_nonce": "",
      "time": 1758873143,
      "triangles_count": 0,
      "update_time": 1758873144,
      "url": "https:...pwmb",
      "user_id": 94829,
      "user_lock_space_id": 25122872,
      "uuid": ""
    },
    {
      "bucket": "workbentch",
      "desc": "",
      "device_type": "pc",
      "estimate": 3927,
      "file_extension": "pwmb",
      "file_source": 6,
      "file_type": 1,
      "filename": "175883400847913800-46f08d44085ed5008a94cdda0adb8d35-68d5ad5874faec36b3bd2c81e0420389.pwmb",
      "gcode_id": 44451758,
      "id": 30657621,
      "img_status": 0,
      "ip": "82.64.136.10",
      "is_delete": 0,
      "is_official_slice": 0,
      "is_parse": 1,
      "is_temp_file": 0,
      "layer_height": 0.05000000074505806,
      "machine_type": 107,
      "material_name": "Resin",
      "md5": "4b4d6c02f8f8c1b1c51df687ee4dcbe4",
      "name_counts": 0,
      "official_file_id": 0,
      "official_file_key": "",
      "official_file_type": -1,
      "old_filename": "skull_cut_19_20_v3.pwmb",
      "origin_file_md5": "4b4d6c02f8f8c1b1c51df687ee4dcbe4",
      "origin_post_id": 0,
      "path": "file/2025/09/26/pwmb/175883400847913800-46f08d44085ed5008a94cdda0adb8d35-68d5ad5874faec36b3bd2c81e0420389.pwmb",
      "plate_number": 0,
      "post_id": 0,
      "printer_image_id": "",
      "printer_names": [
        "Anycubic Photon M3 Plus"
      ],
      "region": "us-east-2",
      "simplify_model": [],
      "size": 46637653,
      "size_x": 0,
      "size_y": 0,
      "size_z": 19.05000114440918,
      "slice_param": {
        "advanced_control": {
          "bott_0": {
            "down_speed": 1,
            "height": 3,
            "z_up_speed": 1
          },
          "bott_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "multi_state_used": 0,
          "normal_0": {
            "down_speed": 1,
            "height": 3,
            "up_speed": 1
          },
          "normal_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "transition_layercount": 10
        },
        "anti_count": 16,
        "basic_control_param": {
          "zdown_speed": 6,
          "zup_height": 6,
          "zup_speed": 6
        },
        "bott_layers": 6,
        "bott_time": 23,
        "bucket_id": "cloud-slice-prod",
        "estimate": 3927,
        "exposure_time": 1.5,
        "image_id": "cloud/2025-09/25/jpg/2ed44f7606fa5fd794086937810f0840.jpg",
        "intelli_mode": 0,
        "layers": 381,
        "machine_name": "Anycubic Photon M3 Plus",
        "machine_param": {
          "name": "Anycubic Photon M3 Plus"
        },
        "machine_tid": 0,
        "material_name": "Basic",
        "material_tid": 0,
        "off_time": 0.5,
        "size_x": 0,
        "size_y": 0,
        "size_z": 19.05000114440918,
        "sliced_md5": "4b4d6c02f8f8c1b1c51df687ee4dcbe4",
        "supplies_usage": 51.47365951538086,
        "zdown_speed": 6,
        "zthick": 0.05000000074505806,
        "zup_height": 6,
        "zup_speed": 6
      },
      "sliceparse_nonce": "68d5ad...957a",
      "source_type": 0,
      "source_user_upload_id": 0,
      "status": 1,
      "stl_user_upload_id": 0,
      "store_type": 2,
      "supplies_usage": 51.47365951538086,
      "thumbnail": "https:....jpg",
      "thumbnail_nonce": "",
      "time": 1758834015,
      "triangles_count": 0,
      "update_time": 1758834016,
      "url": "https:...pwmb",
      "user_id": 94829,
      "user_lock_space_id": 25092807,
      "uuid": ""
    },
    {
      "bucket": "workbentch",
      "desc": "",
      "device_type": "pc",
      "estimate": 3114,
      "file_extension": "pwmb",
      "file_source": 6,
      "file_type": 1,
      "filename": "175874513994727800-80eb1739e42ca165f52268336cdb8b9e-68d45233e74595d521914ed979acb69f.pwmb",
      "gcode_id": 44306216,
      "id": 30553490,
      "img_status": 0,
      "ip": "82.64.136.10",
      "is_delete": 0,
      "is_official_slice": 0,
      "is_parse": 1,
      "is_temp_file": 0,
      "layer_height": 0.05000000074505806,
      "machine_type": 107,
      "material_name": "Resin",
      "md5": "da0964860455c04ea96f7ed4fa8d3dec",
      "name_counts": 0,
      "official_file_id": 0,
      "official_file_key": "",
      "official_file_type": -1,
      "old_filename": "T3d_skull_10_50_v3.pwmb",
      "origin_file_md5": "da0964860455c04ea96f7ed4fa8d3dec",
      "origin_post_id": 0,
      "path": "file/2025/09/25/pwmb/175874513994727800-80eb1739e42ca165f52268336cdb8b9e-68d45233e74595d521914ed979acb69f.pwmb",
      "plate_number": 0,
      "post_id": 0,
      "printer_image_id": "",
      "printer_names": [
        "Anycubic Photon M3 Plus"
      ],
      "region": "us-east-2",
      "simplify_model": [],
      "size": 44851383,
      "size_x": 0,
      "size_y": 0,
      "size_z": 14.350000381469727,
      "slice_param": {
        "advanced_control": {
          "bott_0": {
            "down_speed": 1,
            "height": 3,
            "z_up_speed": 1
          },
          "bott_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "multi_state_used": 0,
          "normal_0": {
            "down_speed": 1,
            "height": 3,
            "up_speed": 1
          },
          "normal_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "transition_layercount": 10
        },
        "anti_count": 16,
        "basic_control_param": {
          "zdown_speed": 6,
          "zup_height": 6,
          "zup_speed": 6
        },
        "bott_layers": 6,
        "bott_time": 23,
        "bucket_id": "cloud-slice-prod",
        "estimate": 3114,
        "exposure_time": 1.5,
        "image_id": "cloud/2025-09/24/jpg/b2ae2b4ccb3f75ac04d03d491ac32977.jpg",
        "intelli_mode": 0,
        "layers": 287,
        "machine_name": "Anycubic Photon M3 Plus",
        "machine_param": {
          "name": "Anycubic Photon M3 Plus"
        },
        "machine_tid": 0,
        "material_name": "Basic",
        "material_tid": 0,
        "off_time": 0.5,
        "size_x": 0,
        "size_y": 0,
        "size_z": 14.350000381469727,
        "sliced_md5": "da0964860455c04ea96f7ed4fa8d3dec",
        "supplies_usage": 44.19231033325195,
        "zdown_speed": 6,
        "zthick": 0.05000000074505806,
        "zup_height": 6,
        "zup_speed": 6
      },
      "sliceparse_nonce": "68d452...f958",
      "source_type": 0,
      "source_user_upload_id": 0,
      "status": 1,
      "stl_user_upload_id": 0,
      "store_type": 2,
      "supplies_usage": 44.19231033325195,
      "thumbnail": "https:....jpg",
      "thumbnail_nonce": "",
      "time": 1758745147,
      "triangles_count": 0,
      "update_time": 1758745147,
      "url": "https:...pwmb",
      "user_id": 94829,
      "user_lock_space_id": 24999108,
      "uuid": ""
    },
    {
      "bucket": "workbentch",
      "desc": "",
      "device_type": "pc",
      "estimate": 11287,
      "file_extension": "pwmb",
      "file_source": 6,
      "file_type": 1,
      "filename": "175847715067534100-dfc891a70d0b3f4077875e73c0a533b5-68d03b5ea4e1ad3f944c607e74d12dd6.pwmb",
      "gcode_id": 43864575,
      "id": 30230841,
      "img_status": 0,
      "ip": "82.64.136.10",
      "is_delete": 0,
      "is_official_slice": 0,
      "is_parse": 1,
      "is_temp_file": 0,
      "layer_height": 0.05000000074505806,
      "machine_type": 107,
      "material_name": "Resin",
      "md5": "3dbf1d60f4052be9f77b653eba9d988c",
      "name_counts": 0,
      "official_file_id": 0,
      "official_file_key": "",
      "official_file_type": -1,
      "old_filename": "raven_skull_28_5_v3.pwmb",
      "origin_file_md5": "3dbf1d60f4052be9f77b653eba9d988c",
      "origin_post_id": 0,
      "path": "file/2025/09/22/pwmb/175847715067534100-dfc891a70d0b3f4077875e73c0a533b5-68d03b5ea4e1ad3f944c607e74d12dd6.pwmb",
      "plate_number": 0,
      "post_id": 0,
      "printer_image_id": "",
      "printer_names": [
        "Anycubic Photon M3 Plus"
      ],
      "region": "us-east-2",
      "simplify_model": [],
      "size": 90987765,
      "size_x": 0,
      "size_y": 0,
      "size_z": 61.54999923706055,
      "slice_param": {
        "advanced_control": {
          "bott_0": {
            "down_speed": 1,
            "height": 3,
            "z_up_speed": 1
          },
          "bott_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "multi_state_used": 0,
          "normal_0": {
            "down_speed": 1,
            "height": 3,
            "up_speed": 1
          },
          "normal_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "transition_layercount": 10
        },
        "anti_count": 16,
        "basic_control_param": {
          "zdown_speed": 6,
          "zup_height": 6,
          "zup_speed": 6
        },
        "bott_layers": 6,
        "bott_time": 23,
        "bucket_id": "cloud-slice-prod",
        "estimate": 11287,
        "exposure_time": 1.5,
        "image_id": "cloud/2025-09/21/jpg/b51bfed45be8f60c74989b25f59a1cc5.jpg",
        "intelli_mode": 0,
        "layers": 1231,
        "machine_name": "Anycubic Photon M3 Plus",
        "machine_param": {
          "name": "Anycubic Photon M3 Plus"
        },
        "machine_tid": 0,
        "material_name": "Basic",
        "material_tid": 0,
        "off_time": 0.5,
        "size_x": 0,
        "size_y": 0,
        "size_z": 61.54999923706055,
        "sliced_md5": "3dbf1d60f4052be9f77b653eba9d988c",
        "supplies_usage": 82.773681640625,
        "zdown_speed": 6,
        "zthick": 0.05000000074505806,
        "zup_height": 6,
        "zup_speed": 6
      },
      "sliceparse_nonce": "68d03b...5eae",
      "source_type": 0,
      "source_user_upload_id": 0,
      "status": 1,
      "stl_user_upload_id": 0,
      "store_type": 2,
      "supplies_usage": 82.773681640625,
      "thumbnail": "https:....jpg",
      "thumbnail_nonce": "",
      "time": 1758477159,
      "triangles_count": 0,
      "update_time": 1758477160,
      "url": "https:...pwmb",
      "user_id": 94829,
      "user_lock_space_id": 24717985,
      "uuid": ""
    },
    {
      "bucket": "workbentch",
      "desc": "",
      "device_type": "pc",
      "estimate": 18136,
      "file_extension": "pwmb",
      "file_source": 6,
      "file_type": 1,
      "filename": "175604142713621300-68ab372e19265e8061ecacca7f491e7e-68ab10d321421c7623b648e0caabeb9f.pwmb",
      "gcode_id": 39999969,
      "id": 27375668,
      "img_status": 0,
      "ip": "82.64.136.10",
      "is_delete": 0,
      "is_official_slice": 0,
      "is_parse": 1,
      "is_temp_file": 0,
      "layer_height": 0.05000000074505806,
      "machine_type": 107,
      "material_name": "Resin",
      "md5": "7b48734a553c345d7b07ea2c718add79",
      "name_counts": 0,
      "official_file_id": 0,
      "official_file_key": "",
      "official_file_type": -1,
      "old_filename": "T3d_skull_13-v2.pwmb",
      "origin_file_md5": "7b48734a553c345d7b07ea2c718add79",
      "origin_post_id": 0,
      "path": "file/2025/08/24/pwmb/175604142713621300-68ab372e19265e8061ecacca7f491e7e-68ab10d321421c7623b648e0caabeb9f.pwmb",
      "plate_number": 0,
      "post_id": 0,
      "printer_image_id": "",
      "printer_names": [
        "Anycubic Photon M3 Plus"
      ],
      "region": "us-east-2",
      "simplify_model": [],
      "size": 257407880,
      "size_x": 0,
      "size_y": 0,
      "size_z": 101.0999984741211,
      "slice_param": {
        "advanced_control": {
          "bott_0": {
            "down_speed": 1,
            "height": 3,
            "z_up_speed": 1
          },
          "bott_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "multi_state_used": 0,
          "normal_0": {
            "down_speed": 1,
            "height": 3,
            "up_speed": 1
          },
          "normal_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "transition_layercount": 10
        },
        "anti_count": 16,
        "basic_control_param": {
          "zdown_speed": 6,
          "zup_height": 6,
          "zup_speed": 6
        },
        "bott_layers": 6,
        "bott_time": 23,
        "bucket_id": "cloud-slice-prod",
        "estimate": 18136,
        "exposure_time": 1.5,
        "image_id": "cloud/2025-08/24/jpg/80cc4e39e83f9bd133d373606dc13e8c.jpg",
        "intelli_mode": 0,
        "layers": 2022,
        "machine_name": "Anycubic Photon M3 Plus",
        "machine_param": {
          "name": "Anycubic Photon M3 Plus"
        },
        "machine_tid": 0,
        "material_name": "Basic",
        "material_tid": 0,
        "off_time": 0.5,
        "size_x": 0,
        "size_y": 0,
        "size_z": 101.0999984741211,
        "sliced_md5": "7b48734a553c345d7b07ea2c718add79",
        "supplies_usage": 218.01727294921875,
        "zdown_speed": 6,
        "zthick": 0.05000000074505806,
        "zup_height": 6,
        "zup_speed": 6
      },
      "sliceparse_nonce": "68ab10...7b5e",
      "source_type": 0,
      "source_user_upload_id": 0,
      "status": 1,
      "stl_user_upload_id": 0,
      "store_type": 2,
      "supplies_usage": 218.01727294921875,
      "thumbnail": "https:....jpg",
      "thumbnail_nonce": "",
      "time": 1756041441,
      "triangles_count": 0,
      "update_time": 1756041444,
      "url": "https:...pwmb",
      "user_id": 94829,
      "user_lock_space_id": 22260421,
      "uuid": ""
    },
    {
      "bucket": "workbentch",
      "desc": "",
      "device_type": "pc",
      "estimate": 15140,
      "file_extension": "pwmb",
      "file_source": 6,
      "file_type": 1,
      "filename": "174902301210375000-de6bf9f8b1875bc8f115ae5cb2d20a14-683ff92419555fc60f96cd8f217df256.pwmb",
      "gcode_id": 30235454,
      "id": 20194528,
      "img_status": 0,
      "ip": "82.64.136.10",
      "is_delete": 0,
      "is_official_slice": 0,
      "is_parse": 1,
      "is_temp_file": 0,
      "layer_height": 0.05000000074505806,
      "machine_type": 0,
      "material_name": "Resin",
      "md5": "f3a4888827db68cb2274183cfd742a2e",
      "name_counts": 0,
      "official_file_id": 0,
      "official_file_key": "",
      "official_file_type": -1,
      "old_filename": "anatomical-heart.pwmb",
      "origin_file_md5": "f3a4888827db68cb2274183cfd742a2e",
      "origin_post_id": 0,
      "path": "file/2025/06/04/pwmb/174902301210375000-de6bf9f8b1875bc8f115ae5cb2d20a14-683ff92419555fc60f96cd8f217df256.pwmb",
      "plate_number": 0,
      "post_id": 0,
      "printer_image_id": "",
      "printer_names": [
        "Anycubic Photon M3 Plus"
      ],
      "region": "us-east-2",
      "simplify_model": [],
      "size": 50281038,
      "size_x": 0,
      "size_y": 0,
      "size_z": 83.80000305175781,
      "slice_param": {
        "advanced_control": {
          "bott_0": {
            "down_speed": 1,
            "height": 3,
            "z_up_speed": 1
          },
          "bott_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "multi_state_used": 0,
          "normal_0": {
            "down_speed": 1,
            "height": 3,
            "up_speed": 1
          },
          "normal_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "transition_layercount": 10
        },
        "anti_count": 1,
        "basic_control_param": {
          "zdown_speed": 6,
          "zup_height": 6,
          "zup_speed": 6
        },
        "bott_layers": 6,
        "bott_time": 23,
        "estimate": 15140,
        "exposure_time": 1.5,
        "image_id": "file/2025/06/04/pwmb/3711a8a27fd1ad3cf57dac0e694b810724e2cf43fc11a278326969eb8f48f9f6.jpg",
        "intelli_mode": 0,
        "layers": 1676,
        "machine_name": "Anycubic Photon M3 Plus",
        "machine_param": {
          "name": "Anycubic Photon M3 Plus"
        },
        "machine_tid": 0,
        "material_name": "Basic",
        "material_tid": 0,
        "off_time": 0.5,
        "size_x": 0,
        "size_y": 0,
        "size_z": 83.80000305175781,
        "sliced_md5": "f3a4888827db68cb2274183cfd742a2e",
        "supplies_usage": 55.676361083984375,
        "zdown_speed": 6,
        "zthick": 0.05000000074505806,
        "zup_height": 6,
        "zup_speed": 6
      },
      "sliceparse_nonce": "683ffa...8188",
      "source_type": 0,
      "source_user_upload_id": 0,
      "status": 1,
      "stl_user_upload_id": 0,
      "store_type": 2,
      "supplies_usage": 55.676361083984375,
      "thumbnail": "https:....jpg",
      "thumbnail_nonce": "",
      "time": 1749023396,
      "triangles_count": 0,
      "update_time": 1749023397,
      "url": "https:...pwmb",
      "user_id": 94829,
      "user_lock_space_id": 16084122,
      "uuid": ""
    },
    {
      "bucket": "workbentch",
      "desc": "",
      "device_type": "pc",
      "estimate": 9175,
      "file_extension": "pwmb",
      "file_source": 6,
      "file_type": 1,
      "filename": "174841701230358600-6e051dcfa3dd409d88d05479e36591d3-6836b9f44a1f052951598aec8d74291b.pwmb",
      "gcode_id": 29407196,
      "id": 19594931,
      "img_status": 0,
      "ip": "82.64.136.10",
      "is_delete": 0,
      "is_official_slice": 0,
      "is_parse": 1,
      "is_temp_file": 0,
      "layer_height": 0.05000000074505806,
      "machine_type": 0,
      "material_name": "Resin",
      "md5": "ee6398b027be71853a481bf8485fbd75",
      "name_counts": 0,
      "official_file_id": 0,
      "official_file_key": "",
      "official_file_type": -1,
      "old_filename": "skull_X47-Y60-5.pwmb",
      "origin_file_md5": "ee6398b027be71853a481bf8485fbd75",
      "origin_post_id": 0,
      "path": "file/2025/05/28/pwmb/174841701230358600-6e051dcfa3dd409d88d05479e36591d3-6836b9f44a1f052951598aec8d74291b.pwmb",
      "plate_number": 0,
      "post_id": 0,
      "printer_image_id": "",
      "printer_names": [
        "Anycubic Photon M3 Plus"
      ],
      "region": "us-east-2",
      "simplify_model": [],
      "size": 131121756,
      "size_x": 0,
      "size_y": 0,
      "size_z": 49.35000228881836,
      "slice_param": {
        "advanced_control": {
          "bott_0": {
            "down_speed": 1,
            "height": 3,
            "z_up_speed": 1
          },
          "bott_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "multi_state_used": 0,
          "normal_0": {
            "down_speed": 1,
            "height": 3,
            "up_speed": 1
          },
          "normal_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "transition_layercount": 10
        },
        "anti_count": 1,
        "basic_control_param": {
          "zdown_speed": 6,
          "zup_height": 6,
          "zup_speed": 6
        },
        "bott_layers": 6,
        "bott_time": 23,
        "estimate": 9175,
        "exposure_time": 1.5,
        "image_id": "file/2025/05/28/pwmb/d35a8a81628a20da15ce5a23880cf11909fd15297e0f0dc7451818adc9ceffff.jpg",
        "intelli_mode": 0,
        "layers": 987,
        "machine_name": "Anycubic Photon M3 Plus",
        "machine_param": {
          "name": "Anycubic Photon M3 Plus"
        },
        "machine_tid": 0,
        "material_name": "Basic",
        "material_tid": 0,
        "off_time": 0.5,
        "size_x": 0,
        "size_y": 0,
        "size_z": 49.35000228881836,
        "sliced_md5": "ee6398b027be71853a481bf8485fbd75",
        "supplies_usage": 171.47491455078125,
        "zdown_speed": 6,
        "zthick": 0.05000000074505806,
        "zup_height": 6,
        "zup_speed": 6
      },
      "sliceparse_nonce": "6836bd...3758",
      "source_type": 0,
      "source_user_upload_id": 0,
      "status": 1,
      "stl_user_upload_id": 0,
      "store_type": 2,
      "supplies_usage": 171.47491455078125,
      "thumbnail": "https:....jpg",
      "thumbnail_nonce": "",
      "time": 1748418016,
      "triangles_count": 0,
      "update_time": 1748418017,
      "url": "https:...pwmb",
      "user_id": 94829,
      "user_lock_space_id": 15559448,
      "uuid": ""
    },
    {
      "bucket": "workbentch",
      "desc": "",
      "device_type": "pc",
      "estimate": 12318,
      "file_extension": "pwmb",
      "file_source": 6,
      "file_type": 1,
      "filename": "174669030397387800-d29b2a115ea68e602586b71242cb36fc-681c60ffedc423a458a2f0b822b14ea7.pwmb",
      "gcode_id": 27084794,
      "id": 17880625,
      "img_status": 0,
      "ip": "82.64.136.10",
      "is_delete": 0,
      "is_official_slice": 0,
      "is_parse": 1,
      "is_temp_file": 0,
      "layer_height": 0.05000000074505806,
      "machine_type": 0,
      "material_name": "Resin",
      "md5": "752ba83586bf17c0afcf4268cc89d044",
      "name_counts": 0,
      "official_file_id": 0,
      "official_file_key": "",
      "official_file_type": -1,
      "old_filename": "skull_X67-Y85-v3.pwmb",
      "origin_file_md5": "752ba83586bf17c0afcf4268cc89d044",
      "origin_post_id": 0,
      "path": "file/2025/05/08/pwmb/174669030397387800-d29b2a115ea68e602586b71242cb36fc-681c60ffedc423a458a2f0b822b14ea7.pwmb",
      "plate_number": 0,
      "post_id": 0,
      "printer_image_id": "",
      "printer_names": [
        "Anycubic Photon M3 Plus"
      ],
      "region": "us-east-2",
      "simplify_model": [],
      "size": 96218750,
      "size_x": 0,
      "size_y": 0,
      "size_z": 67.5,
      "slice_param": {
        "advanced_control": {
          "bott_0": {
            "down_speed": 1,
            "height": 3,
            "z_up_speed": 1
          },
          "bott_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "multi_state_used": 0,
          "normal_0": {
            "down_speed": 1,
            "height": 3,
            "up_speed": 1
          },
          "normal_1": {
            "down_speed": 5,
            "height": 3,
            "up_speed": 5
          },
          "transition_layercount": 10
        },
        "anti_count": 1,
        "basic_control_param": {
          "zdown_speed": 6,
          "zup_height": 6,
          "zup_speed": 6
        },
        "bott_layers": 6,
        "bott_time": 23,
        "estimate": 12318,
        "exposure_time": 1.5,
        "image_id": "file/2025/05/08/pwmb/145b8e3eee96199b6ef02274ffd7c4346b3c0a3d43080cd2be14148915f7cb49.jpg",
        "intelli_mode": 0,
        "layers": 1350,
        "machine_name": "Anycubic Photon M3 Plus",
        "machine_param": {
          "name": "Anycubic Photon M3 Plus"
        },
        "machine_tid": 0,
        "material_name": "Basic",
        "material_tid": 0,
        "off_time": 0.5,
        "size_x": 0,
        "size_y": 0,
        "size_z": 67.5,
        "sliced_md5": "752ba83586bf17c0afcf4268cc89d044",
        "supplies_usage": 127.17839050292969,
        "zdown_speed": 6,
        "zthick": 0.05000000074505806,
        "zup_height": 6,
        "zup_speed": 6
      },
      "sliceparse_nonce": "681c63...871d",
      "source_type": 0,
      "source_user_upload_id": 0,
      "status": 1,
      "stl_user_upload_id": 0,
      "store_type": 2,
      "supplies_usage": 127.17839050292969,
      "thumbnail": "https:....jpg",
      "thumbnail_nonce": "",
      "time": 1746691040,
      "triangles_count": 0,
      "update_time": 1746691041,
      "url": "https:...pwmb",
      "user_id": 94829,
      "user_lock_space_id": 14086435,
      "uuid": ""
    }
  ],
  "msg": "\u8bf7\u6c42\u88ab\u63a5\u53d7",
  "pageData": {
    "page": 2,
    "page_count": 10,
    "total": 20
  }
}
```

### `POST /p/p/workbench/api/work/index/getDowdLoadUrl`
- Capture: non
- Modele JSON attendu (source `api_map.json`):
```json
{
  "code": 1,
  "data": "<signed_s3_url>"
}
```

### `POST /p/p/workbench/api/work/index/getUploadStatus`
- Capture: non
- Modele JSON attendu (source `api_map.json`):
```json
{
  "code": 1,
  "data": {
    "gcode_id": "<gcode_id>",
    "status": 1
  }
}
```

### `POST /p/p/workbench/api/work/index/getUserStore`
- Capture: oui (3 echantillon(s))
- Sources: har:uc.makeronline.com.har x1, log:cloud_Log.log.1 x2
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (object)
  - `data.total` (str) example="2.00GB"
  - `data.total_bytes` (int) example=2147483648
  - `data.used` (str) example="1.13GB"
  - `data.used_bytes` (int) example=1218090634
  - `data.user_file_exists` (bool) example=true
  - `msg` (str) example="????"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": {
    "total": "2.00GB",
    "total_bytes": 2147483648,
    "used": "1.13GB",
    "used_bytes": 1218090634,
    "user_file_exists": true
  },
  "msg": "????"
}
```

### `POST /p/p/workbench/api/work/index/renameFile`
- Capture: non
- Modele JSON attendu (source `api_map.json`):
```json
{
  "code": 1,
  "data": "<name>"
}
```

### `POST /p/p/workbench/api/work/index/userFiles`
- Capture: oui (1 echantillon(s))
- Sources: log:cloud_Log.log.1 x1
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (object)
  - `data.total` (str) example="2.00GB"
  - `data.total_bytes` (int) example=2147483648
  - `data.used` (str) example="1.26GB"
  - `data.used_bytes` (int) example=1355899303
  - `data.user_file_exists` (bool) example=true
  - `msg` (str) example="????"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": {
    "total": "2.00GB",
    "total_bytes": 2147483648,
    "used": "1.26GB",
    "used_bytes": 1355899303,
    "user_file_exists": true
  },
  "msg": "????"
}
```

### `POST /p/p/workbench/api/work/operation/sendOrder`
- Capture: oui (1 echantillon(s))
- Sources: log:cloud_Log.log.1 x1
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (object)
  - `data.task_id` (str) example="70995094"
  - `msg` (str) example="????"
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": {
    "task_id": "70995094"
  },
  "msg": "????"
}
```

### `POST /p/p/workbench/api/work/printer/Info`
- Capture: non
- Modele JSON: non disponible dans les sources analysees.

### `GET /p/p/workbench/api/work/printer/getPrinters`
- Capture: oui (33 echantillon(s))
- Sources: log:cloud_Log.log x5, log:cloud_Log.log.1 x28
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (list)
  - `data[]` (object)
  - `data[].color` (list)
  - `data[].color[]` (empty)
  - `data[].create_time` (int) example=1708449350
  - `data[].delete` (int) example=0
  - `data[].delete_time` (int) example=0
  - `data[].description` (str) example="A7F6-B0FF-F706-3D49"
  - `data[].device_status` (int) example=1
  - `data[].features` (null)
  - `data[].id` (int) example=42859
  - `data[].img` (str) example="https://cdn.cloud-platform.anycubic.com/php/img/4/m3plus.png"
  - `data[].is_clean_plate` (int) example=0
  - `data[].is_printing` (int) example=2
  - `data[].key` (str) example="35b1681ce52f58f18feffd6880a43d36"
  - `data[].label_id` (int) example=0
  - `data[].label_name` (str) example=""
  - `data[].last_update_time` (int) example=1770805804006
  - `data[].machine_data` (object)
  - `data[].machine_data.anti_max` (int) example=8
  - `data[].machine_data.format` (str) example="pw0Img"
  - `data[].machine_data.name` (str) example="Anycubic Photon M3 Plus"
  - `data[].machine_data.pixel` (float) example=34.4
  - `data[].machine_data.res_x` (int) example=5760
  - `data[].machine_data.res_y` (int) example=3600
  - `data[].machine_data.size_x` (float) example=197.0
  - `data[].machine_data.size_y` (float) example=122.8
  - `data[].machine_data.size_z` (float) example=245.0
  - `data[].machine_data.suffix` (str) example="pwmb"
  - `data[].machine_mac` (str) example=""
  - `data[].machine_type` (int) example=107
  - `data[].material_type` (str) example="\u6811\u8102"
  - `data[].material_used` (str) example="23260.42ml"
  - `data[].max_box_num` (int) example=0
  - `data[].model` (str) example="Anycubic Photon M3 Plus"
  - `data[].msg` (str) example=""
  - `data[].multi_color_box` (list)
  - `data[].multi_color_box[]` (empty)
  - `data[].name` (str) example="Anycubic Photon M3 Plus"
  - `data[].nonce` (str) example=""
  - `data[].print_totaltime` (str) example="647\u5c0f\u65f69\u5206"
  - `data[].ready_status` (int) example=0
  - `data[].reason` (str) example="busy"
  - `data[].status` (int) example=1
  - `data[].type` (str) example="LCD"
  - `data[].type_function_ids` (list)
  - `data[].type_function_ids[]` (int) example=7
  - `data[].user_id` (int) example=94829
  - `data[].version` (null)
  - `data[].video_taskid` (int) example=0
  - `msg` (str) example="\u8bf7\u6c42\u88ab\u63a5\u53d7"
  - `pageData` (object)
  - `pageData.count` (int) example=1
  - `pageData.page` (int) example=1
  - `pageData.page_count` (int) example=1000
  - `pageData.total` (int) example=1
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": [
    {
      "color": [],
      "create_time": 1708449350,
      "delete": 0,
      "delete_time": 0,
      "description": "A7F6-B0FF-F706-3D49",
      "device_status": 2,
      "features": null,
      "id": 42859,
      "img": "https://cdn.cloud-platform.anycubic.com/php/img/4/m3plus.png",
      "is_clean_plate": 0,
      "is_printing": 1,
      "key": "35b1681ce52f58f18feffd6880a43d36",
      "label_id": 0,
      "label_name": "",
      "last_update_time": 1770662731054,
      "machine_data": {
        "anti_max": 8,
        "format": "pw0Img",
        "name": "Anycubic Photon M3 Plus",
        "pixel": 34.4,
        "res_x": 5760,
        "res_y": 3600,
        "size_x": 197.0,
        "size_y": 122.8,
        "size_z": 245.0,
        "suffix": "pwmb"
      },
      "machine_mac": "",
      "machine_type": 107,
      "material_type": "\u6811\u8102",
      "material_used": "23127.1ml",
      "max_box_num": 0,
      "model": "Anycubic Photon M3 Plus",
      "msg": "",
      "multi_color_box": [],
      "name": "Anycubic Photon M3 Plus",
      "nonce": "",
      "print_totaltime": "642\u5c0f\u65f653\u5206",
      "ready_status": 0,
      "reason": "offline",
      "status": 1,
      "type": "LCD",
      "type_function_ids": [
        7,
        22
      ],
      "user_id": 94829,
      "version": null,
      "video_taskid": 0
    }
  ],
  "msg": "\u8bf7\u6c42\u88ab\u63a5\u53d7",
  "pageData": {
    "count": 1,
    "page": 1,
    "page_count": 1000,
    "total": 1
  }
}
```

### `GET /p/p/workbench/api/work/project/getProjects`
- Capture: oui (32 echantillon(s))
- Sources: log:cloud_Log.log x5, log:cloud_Log.log.1 x27
- Status observes: 200
- Champs JSON observes:
  - `code` (int) example=1
  - `data` (list)
  - `data[]` (object)
  - `data[].auto_operation` (null)
  - `data[].connect_status` (int) example=0
  - `data[].create_time` (int) example=1770805803
  - `data[].delete` (int) example=0
  - `data[].device_message` (null)
  - `data[].device_status` (int) example=1
  - `data[].dual_platform_mode_enable` (int) example=0
  - `data[].end_time` (int) example=0
  - `data[].estimate` (int) example=11038
  - `data[].evoke_from` (int) example=0
  - `data[].gcode_id` (int) example=71469071
  - `data[].gcode_name` (str) example="raven_skull_19_v3"
  - `data[].id` (int) example=72244987
  - `data[].image_id` (str) example="https:....jpg"
  - `data[].img` (str) example="https:....jpg"
  - `data[].is_comment` (int) example=0
  - `data[].is_makeronline_file` (int) example=0
  - `data[].is_web_evoke` (int) example=0
  - `data[].ischeck` (int) example=2
  - `data[].key` (str) example="35b1681ce52f58f18feffd6880a43d36"
  - `data[].last_update_time` (int) example=1770808141169
  - `data[].localtask` (null)
  - `data[].machine_class` (int) example=0
  - `data[].machine_name` (str) example="Anycubic Photon M3 Plus"
  - `data[].machine_type` (int) example=107
  - `data[].material` (str) example="4.6219687461853"
  - `data[].material_type` (int) example=10
  - `data[].model` (int) example=51422349
  - `data[].monitor` (null)
  - `data[].pause` (int) example=0
  - `data[].post_title` (null)
  - `data[].print_status` (int) example=1
  - `data[].print_time` (int) example=38
  - `data[].printed` (int) example=1
  - `data[].printer_id` (int) example=42859
  - `data[].printer_name` (str) example="Anycubic Photon M3 Plus"
  - `data[].progress` (int) example=14
  - `data[].project_type` (int) example=1
  - `data[].reason` (int) example=0
  - `data[].remain_time` (int) example=218
  - `data[].settings` (null|str) example="{\"task...:\"\"}"
  - `data[].signal_strength` (int) example=-1
  - `data[].slice_data` (null)
  - `data[].slice_end_time` (int) example=0
  - `data[].slice_param` (str) example="{\"adva...s\"}}"
  - `data[].slice_result` (str) example="{\"adva...1.0}"
  - `data[].slice_start_time` (int) example=0
  - `data[].slice_status` (int) example=0
  - `data[].source` (str) example="web"
  - `data[].start_time` (int) example=1770805803
  - `data[].status` (int) example=0
  - `data[].taskid` (int) example=72244987
  - `data[].total_time` (int|str) example="???..."
  - `data[].type` (str) example="LCD"
  - `data[].user_id` (int) example=94829
  - `msg` (str) example="?????"
  - `pageData` (object)
  - `pageData.count` (int) example=1
  - `pageData.page` (int) example=1
  - `pageData.page_count` (int) example=10
- JSON complet observe (echantillon le plus riche):
```json
{
  "code": 1,
  "data": [
    {
      "auto_operation": null,
      "connect_status": 0,
      "create_time": 1770805803,
      "delete": 0,
      "device_message": null,
      "device_status": 1,
      "dual_platform_mode_enable": 0,
      "end_time": 0,
      "estimate": 11038,
      "evoke_from": 0,
      "gcode_id": 71469071,
      "gcode_name": "raven_skull_19_v3",
      "id": 72244987,
      "image_id": "https:....jpg",
      "img": "https:....jpg",
      "is_comment": 0,
      "is_makeronline_file": 0,
      "is_web_evoke": 0,
      "ischeck": 2,
      "key": "35b1681ce52f58f18feffd6880a43d36",
      "last_update_time": 1770808141169,
      "localtask": null,
      "machine_class": 0,
      "machine_name": "Anycubic Photon M3 Plus",
      "machine_type": 107,
      "material": "4.6219687461853",
      "material_type": 10,
      "model": 51422349,
      "monitor": null,
      "pause": 0,
      "post_title": null,
      "print_status": 1,
      "print_time": 38,
      "printed": 1,
      "printer_id": 42859,
      "printer_name": "Anycubic Photon M3 Plus",
      "progress": 14,
      "project_type": 1,
      "reason": 0,
      "remain_time": 218,
      "settings": "{\"task...:\"\"}",
      "signal_strength": -1,
      "slice_data": null,
      "slice_end_time": 0,
      "slice_param": "{\"adva...s\"}}",
      "slice_result": "{\"adva...1.0}",
      "slice_start_time": 0,
      "slice_status": 0,
      "source": "web",
      "start_time": 1770805803,
      "status": 0,
      "taskid": 72244987,
      "total_time": "???...",
      "type": "LCD",
      "user_id": 94829
    }
  ],
  "msg": "?????",
  "pageData": {
    "count": 1,
    "page": 1,
    "page_count": 10
  }
}
```

### `GET https://uc.makeronline.com/api/logout`
- Capture: non
- Modele JSON: non disponible dans les sources analysees.

### `GET https://uc.makeronline.com/login/oauth/authorize`
- Capture: non
- Modele JSON: non disponible dans les sources analysees.

### Couverture
- Endpoints catalogues: 25
- Endpoints avec JSON capture: 16
- Endpoints sans capture JSON: 9

---
