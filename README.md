# VaultChain

**A visual frontend prototype for Blockchain-Based Secure File Sharing and Access Control**

VaultChain is a React + TypeScript demonstration built for an academic major project. It explores the user experience for an institutional, blockchain-governed document platform. This repository is an **interactive frontend milestone**, not a deployed storage, encryption, identity, or blockchain system.

## Quick start (Windows)

You need **Node.js 20.19+ or 22.12+** and an internet connection for the first `npm install`.

1. Extract the ZIP archive.
2. Open the `VaultChain_Frontend` folder in VS Code.
3. Open **Terminal → New Terminal** and run:

```powershell
npm install
npm run dev
```

4. Open the **Local** URL printed by Vite (normally `http://localhost:5173`).
5. Select **Enter workspace** and choose **Student workspace** or **Administrator workspace**.

### Other commands

```powershell
npm run build      # TypeScript check + production build
npm run preview    # Serve the production build
npm run test       # Unit tests for display helpers
npm run typecheck  # TypeScript only
```

> If Windows PowerShell blocks the `npm` script, use Command Prompt or run `npm.cmd install` and `npm.cmd run dev` instead. Do not change your system-wide execution policy just for this project.

## University demo walkthrough (3–5 minutes)

1. Visit the landing page. Scroll through the visual overview of document ownership, distributed storage and governance.
2. Click **Enter workspace**, select **Student workspace** and open the dashboard.
3. Click **Upload files**; select a small file from your computer. The browser saves the file in IndexedDB; its metadata appears in **My Files**.
4. From **My Files**, use the three-dot menu to **Download**, **Rename**, **Move**, **Star**, or **Manage sharing**. For sharing, enter an email like `priya@university.edu` and grant demo access.
5. Open **Shared access** to review or revoke that permission.
6. Open **Blockchain Activity** to see generated **SIM-** event identifiers, explicitly marked as simulations.
7. Open **Storage Network** to explore the illustrative storage topology and equal-quota node cards.
8. Sign out; sign back in with the **Administrator** demo role. Open **Administration** and simulate a node entering maintenance. The event will appear in the activity view.

For the demonstration, upload your own small file and then download it again. Seed files are **metadata-only examples**; they cannot be downloaded.

## What works today

| Feature | Implementation in this repository |
| --- | --- |
| Landing / product overview | Original motion-enhanced responsive page |
| Demo sign-in | Student and administrator **visual session roles** using `sessionStorage` |
| File upload and download | Real local file bytes stored in browser `IndexedDB` (max 12 MB per file) |
| File metadata | `localStorage` persistence |
| Folder organization | Create folder, move file, filter, rename, star, trash, restore and permanently delete |
| Demo sharing | Institution-domain (`@university.edu`) access records; grant/revoke reflected in the UI |
| Ledger activity | Local simulated event log with `SIM-` identifiers |
| Storage network | Sample node states, quotas and topology visualization; no actual file fragmentation |
| Admin controls | Local simulated node maintenance and demo-data reset |
| Visual behavior | Responsive layouts, CSS-generated graphics, animations, reduced-motion support |

## Explicit limitations

- **No real blockchain, consensus, smart contracts, wallets, signing identities, or transaction finality.** Events are local UI simulations.
- **No encryption, distributed fragment coding, threshold-key management, recoverability, or integrity proofs.** Do not upload sensitive documents assuming they are encrypted.
- **No Google Drive API or other cloud-provider integration.** Uploaded bytes remain in this browser profile's IndexedDB.
- **No secure login or institutional SSO.** The demo-role selector is only a UI walkthrough. Do not treat role restrictions as security guarantees.
- **No real emails or third-party sharing** are sent, even when a `@university.edu` address is entered.
- **Sample files contain metadata, not file bytes.** Test downloads with files you upload yourself.
- Browser storage is not a durable backup. Clearing site data/private browsing can delete uploaded files and activity.

## Architecture and components

The proposed full platform has 11 requirement components. The prototype surfaces them at a **product-interface** level, not as working infrastructure:

1. Distributed storage model
2. Encryption and key management
3. Blockchain governance and authorization
4. File processing, coding and reconstruction
5. Storage-node management and lifecycle
6. Data-transfer and execution orchestration
7. Metadata, indexing and state management
8. Cloud-provider integration and credentials
9. User identity and application interface
10. Monitoring, auditing and security operations
11. Administration and deployment management

Backend engineering starts after the integrated architecture, inter-component consistency and feasibility analysis are completed. Existing visual simulations are not a substitute for those systems.

## Project structure

```text
src/
  components/  # Brand, network visualization, dialogs, file tables
  context/     # Demo session and browser-local workspace state
  data/        # Explicitly fictional seed files, nodes, and transactions
  lib/         # IndexedDB blob handling and display helpers
  pages/       # Landing, SignIn, Dashboard, Files, Shared, StorageNetwork, BlockchainActivity, Admin
  App.tsx      # Routes
  index.css    # Tailwind layers + custom art / motion / layout styles
```

## GitHub setup

From the extracted folder:

```powershell
git init
git add .
git commit -m "feat: VaultChain browser-local frontend prototype"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Replace the remote URL with the GitHub repository you create. Do **not** commit `node_modules/`, `dist/`, local secrets, or real participant documents. `.gitignore` already excludes build artifacts and dependencies.

## Notes on visual design

The experience uses modern product-page principles—generous typography, motion, depth, interactive graphics, and editorial layout—without copying any Apple imagery, branded assets, or proprietary interface code. All page artwork is composed of original CSS and SVG shapes.

**Academic project:** Blockchain-Based Secure File Sharing and Access Control  
**Project ID:** 26P_3CSE071  
**Project guide:** Dr. Neeraj Pratap
