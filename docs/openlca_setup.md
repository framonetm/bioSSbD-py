# Setting up openLCA 2 for bioSSbD-py

bioSSbD-py talks to the openLCA 2 desktop application through its IPC server
(`src/biossbd/connectors/openlca.py`). These steps take about 15–20 minutes.

## 1. Install openLCA 2 (free, MPL-2.0)
1. Download the latest **openLCA 2.x for Windows** from <https://www.openlca.org/download/>
   (free registration may be required).
2. Run the installer, or unzip the zip version to a folder such as `C:\Users\<user>\openLCA`.
3. Start openLCA once. It creates its data folder in `C:\Users\<user>\openLCA-data-1.4`.

## 2. Download free data from openLCA Nexus
1. Create a free account at <https://nexus.openlca.org>.
2. Under *Databases*, filter for free ones and download:
   - **USLCI** (US Life Cycle Inventory): materials, transport (lorry, rail, ship in t·km) and electricity.
     A good first database.
   - **openLCA LCIA methods** (free pack with EF 3.x, ReCiPe, TRACI, ...). Needed for GHG and other impacts.
3. Optional: **Agribalyse** for agricultural and food inputs.

## 3. Load the data into openLCA
1. **File > Import > Database** (or right-click the Navigation panel > *Restore database*) and choose the
   USLCI file (`.zolca`).
2. **Double-click the database** in the Navigation panel to open it (it is shown in bold when open).
3. Right-click the open database > **Import > File** and choose the LCIA methods file. If asked for a
   format, pick JSON-LD and keep the defaults.
4. Check that *Indicators and parameters > Impact assessment methods* is not empty.

## 4. Start the IPC server
1. With the database open: **Tools > Developer tools > IPC Server**.
2. Make sure the port is **8080** and click the **start (▶) button**. Opening the dialog alone does not
   start it.
3. If Windows Firewall asks about Java/openLCA, click **Allow**.
4. Keep openLCA running. The server stops when openLCA or the database is closed.

openLCA must run on the same computer and under the same user as bioSSbD-py.

## 5. Check the connection
In PowerShell:

```powershell
Test-NetConnection localhost -Port 8080 -InformationLevel Quiet   # True = server is up
.\.venv\Scripts\python.exe -c "from biossbd.connectors.openlca import OpenLCA; o = OpenLCA(8080); print(o.ping(), len(o.impact_methods()), 'methods')"
```

If it prints `False`, repeat step 4.

## 6. Use it in the GUI
1. `.\.venv\Scripts\python.exe -m biossbd.cli gui` and open <http://localhost:8501>.
2. Go to **5 · Environmental (LCA)**, choose **openLCA 2**, then click **Connect**.
3. Either calculate an existing product system, or build an **inventory per alternative**: search
   processes (materials in kg, transport in t·km, electricity in kWh), add amounts per functional unit
   *with their source*, choose an LCIA method, then **Calculate inventory** and **Attach totals to each alternative**.

The first calculation can take a minute while openLCA builds its matrices; later ones are faster.

Note: each inventory process is calculated directly as a process (no database change). If the openLCA
server refuses a process as target, bioSSbD-py creates a product system from that process instead, which
is stored in the open database.
