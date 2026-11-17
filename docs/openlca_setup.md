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
   - **USLCI** (US Life Cycle Inventory): materials, transport (truck, rail, barge in t·km) and electricity.
     A good first database.
   - **LCIA methods that use the same elementary-flow list as the database.** Needed for GHG and other
     impacts. The methods match flows by UUID, not by name, so a mismatched pack gives **0 for every
     impact** with no error from openLCA.

> **Verified on 2026-11-17 (openLCA 2, USLCI):** the generic *openLCA LCIA methods* pack (EF 3.x, IPCC 2021,
> TRACI 2.1, CML-IA, ReCiPe, ...) uses openLCA/ILCD flow UUIDs, while USLCI uses the Federal LCA Commons
> Elementary Flow List (FEDEFL). Of 3813 non-zero flows in a truck-transport inventory, the best pack method
> (EF 3.1) characterised 28 and IPCC 2021 none, so the GWP of 1 t·km came out as 0 instead of the fossil CO2
> (0.32 kg) in the inventory. For USLCI, use LCIA methods published for FEDEFL flows (Federal LCA Commons), or
> a database that ships with matching methods. bioSSbD-py now raises `MethodMismatchError` when all impacts are
> 0 but the inventory has emissions; a *partial* match (some factors found) cannot be detected that way, so
> run the check in section 5 when you change database or method.
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

Then check that the LCIA method fits the database: calculate 1 unit of a process you know emits CO2 and
see which of its flows the method characterises (replace the two names as needed):

```powershell
.\.venv\Scripts\python.exe -c "from biossbd.connectors.openlca import OpenLCA; o = OpenLCA(8080); p = o.processes('Transport, combination truck; average fuel mix')[0]; m = [x for x in o.impact_methods() if x.name == 'IPCC 2021'][0]; print(o.method_coverage(p.id, m.id))"
```

`matched` near 0 (USLCI with the generic pack gave `'matched': 0, 'flows': 3813` for IPCC 2021) means the
method and the database use different elementary-flow lists (see the note in section 2): pick or import a
matching method before using results. `largest_unmatched` shows the biggest flows the method ignores; USLCI
also reports some cut-off technosphere flows there, which no method characterises.

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
