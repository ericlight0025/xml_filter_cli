# XML Key Filter

以 Python 製作的 XML 篩選工具，支援 Rich CLI、XML 結構查看與深色 GUI。

## 功能

- 只保留指定 `<key>` 的資料節點。
- 最外層 XML 固定為 `<datalist>`。
- 外圍 list tag 可輸入，預設為 `data`。
- 支援完整 XML 結構與內容查看。
- GUI 支援選檔、深色模式、XML 語法亮色、完整預覽與安全另存。
- 預設不覆蓋原始 XML；輸出檔已存在時需要明確確認覆蓋。

## XML 結構範例

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

上述結構的外圍 list tag 是 `data`，可篩選的 key 是 `A001` 或 `A002`。

## 啟動方式

所有指令均在 `xml_filter_cli` 目錄下執行，並使用工作區指定 Python：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe
```

### Rich 總選單

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe menu_cli.py
```

選單項目：

1. `XML Key Filter`：互動式篩選 XML。
2. `XML Content Inspector`：查看根標籤、子標籤統計與完整 XML。
3. `XML Filter GUI`：開啟桌面視窗。
4. 離開。

### GUI（推薦日常手動操作）

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe xml_filter_gui.py
```

GUI 操作順序：

1. 點擊「選擇 XML」，選取既有 XML 檔案。
2. 下方會顯示完整 XML，並以深色編輯器風格標示 tag、屬性、值與註解。
3. 輸入「外圍 list tag」，一般範例填 `data`。
4. 輸入「保留 key」，例如 `A002`。
5. 點擊「篩選並另存 XML」，選擇輸出位置。

篩選完成後，GUI 會自動載入並顯示新產生的結果 XML。

### XML Content Inspector

從總選單選 `2`，或直接執行：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe inspect_xml.py examples\input.xml
```

它會顯示完整 XML 內容，方便先確認要填的外圍 list tag，例如 `<data>`。

### 參數模式

適合批次或自動化流程：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe filter_xml.py "XML檔案路徑" A002
```

指定外圍 list tag：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe filter_xml.py input.xml X002 --item-tag record
```

指定輸出檔：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe filter_xml.py input.xml A002 --output result.xml
```

若輸出檔已存在，必須加入 `--force`：

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe filter_xml.py input.xml A002 --output result.xml --force
```

## 測試資料

範例輸入檔：

```text
examples\input.xml
```

可用下列條件測試：

```text
外圍 list tag：data
保留 key：A002
```

## 相依套件

- Python 標準函式庫：`tkinter`、`xml.etree.ElementTree`。
- `rich`：Rich CLI 顯示。

如需在其他環境安裝相依套件：

```text
python -m pip install -r requirements.txt
```

## 執行測試

```text
C:\DevWorkspace\googletts_package_shorts_venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 注意事項

- XML 篩選只處理 `<datalist>` 直接下方、指定外圍 list tag 的節點。
- 找不到指定 key 時不會建立空的輸出檔。
- GUI 與 Inspector 會完整載入 XML；非常大的 XML 檔案會需要較多記憶體與顯示時間。
