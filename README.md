# XML Key Filter Studio

Python XML 篩選工具，提供 Rich CLI、結構 Inspector 與深色 GUI。適合手動檢查 XML，也保留可批次執行的參數模式。

## 主要功能

- 自動偵測 root tag、外圍 list tag 與候選 key tag。
- 支援單一或多個 key；可用換行、逗號或分號分隔。
- 篩選前顯示資料總數、保留筆數與刪除筆數。
- 原始檔與輸出檔分開顯示，不會把結果檔誤當成下一次輸入。
- 支援 XML namespace，使用 tag 的 local name 篩選。
- GUI 提供深色 XML 語法亮色、行號、搜尋、上一筆／下一筆與 list 節點摺疊。
- 20 MB 以上自動切換大型檔案模式：串流篩選並限制畫面預覽量。
- 使用暫存檔完成後才替換輸出，找不到 key 時不會建立空檔。
- 預設不覆蓋原始 XML；覆蓋輸出檔前需要明確確認。

## XML 範例

```xml
<datalist>
    <data>
        <key>A001</key>
        <name>第一筆資料</name>
    </data>
    <data>
        <key>A002</key>
        <name>第二筆資料</name>
    </data>
</datalist>
```

自動偵測結果：

```text
root tag：datalist
list tag：data
候選 key tags：key、name
```

## Python 環境

所有指令均在 `xml_filter_cli` 目錄執行，工作區預設 Python：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe
```

## GUI（推薦日常操作）

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe xml_filter_gui.py
```

操作流程：

1. 點擊「選擇 XML」；GUI 會自動分析 root、list 與 key tag。
2. 確認自動選出的 tag，必要時可手動修改。
3. 在多行輸入區填入一個或多個 key。
4. 點擊「預覽篩選結果」。
5. 確認總數、保留數、刪除數與 XML 結果。
6. 「確認並另存 XML」會在有效預覽後才啟用。

多 key 範例：

```text
A001
A003
A008
```

### GUI XML 編輯器

- tag、屬性、值、註解使用不同顏色。
- 左側顯示行號。
- 可搜尋文字並切換上一筆／下一筆。
- 「摺疊 list 節點」會收合目前 list tag 的內容；「展開全部」可還原。
- 「顯示原始 XML」與篩選預覽可隨時切換。

## Rich 總選單

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe menu_cli.py
```

選單：

1. `XML Key Filter`：自動偵測 tag、預覽並篩選。
2. `XML Content Inspector`：查看結構、筆數與 XML 內容。
3. `XML Filter GUI`：開啟桌面 GUI。
4. 離開。

## XML Content Inspector

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe inspect_xml.py examples\input.xml
```

Inspector 會顯示：

- 檔案大小與 root tag。
- root 下的直接子標籤與數量。
- 每種 list tag 內的候選欄位 tag。
- 小型 XML 的完整內容。
- 大型 XML 的前 50 個直接子節點。

可調整大型檔案門檻：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe inspect_xml.py input.xml --large-threshold-mb 50
```

## CLI 參數模式

單一 key：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe filter_xml.py input.xml A002
```

多個 key：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe filter_xml.py input.xml "A001,A003,A008"
```

指定完整 tag 設定與輸出檔：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe filter_xml.py input.xml "X001;X002" --root-tag records --item-tag record --key-tag code --output result.xml
```

只預覽、不寫檔：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe filter_xml.py input.xml A002 --preview-only
```

允許覆蓋既有輸出：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe filter_xml.py input.xml A002 --output result.xml --force
```

調整大型檔案串流門檻：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe filter_xml.py input.xml A002 --large-threshold-mb 50
```

## Namespace

下列 XML 可直接用 `datalist`、`data`、`key` 篩選，不需要輸入 `{urn:example}data`：

```xml
<ns:datalist xmlns:ns="urn:example">
    <ns:data>
        <ns:key>N001</ns:key>
    </ns:data>
</ns:datalist>
```

## 大型 XML 模式

預設門檻為 20 MB：

- 結構分析使用 `iterparse`，不整包載入。
- 篩選結果以串流方式寫入暫存檔，成功後才移到輸出路徑。
- GUI 與 Inspector 為避免凍結，只顯示前 50 個直接子節點或匹配節點。
- 保留／刪除筆數仍會統計完整檔案，不是抽樣結果。

## 測試資料

```text
examples\input.xml
```

建議測試條件：

```text
root tag：datalist
list tag：data
key tag：key
保留 keys：A002
```

## 相依套件

- Python 標準函式庫：`tkinter`、`xml.etree.ElementTree`。
- `rich`：Rich CLI 與 Inspector 顯示。

```text
python -m pip install -r requirements.txt
```

## 執行測試

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 注意事項

- 篩選範圍是 root 直接下方、符合指定 list tag 的節點。
- key tag 預設在 list 節點的直接子層。
- XML 會以 UTF-8 重新輸出，縮排與原始檔可能不同。
- 非 list tag 的 root 直接子節點會保留。
