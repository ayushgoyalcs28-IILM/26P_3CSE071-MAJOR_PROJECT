import {BrowserRouter,Navigate,Route,Routes} from 'react-router-dom';
import {VaultProvider} from './context/VaultContext';
import Landing from './pages/Landing';
import SignIn from './pages/SignIn';
import AppShell from './pages/AppShell';
import Dashboard from './pages/Dashboard';
import Files from './pages/Files';
import Shared from './pages/Shared';
import StorageNetwork from './pages/StorageNetwork';
import BlockchainActivity from './pages/BlockchainActivity';
import Admin from './pages/Admin';
export default function App(){return <VaultProvider><BrowserRouter><Routes><Route path="/" element={<Landing/>}/><Route path="/signin" element={<SignIn/>}/><Route path="/app" element={<AppShell/>}><Route index element={<Dashboard/>}/><Route path="files" element={<Files/>}/><Route path="shared" element={<Shared/>}/><Route path="network" element={<StorageNetwork/>}/><Route path="ledger" element={<BlockchainActivity/>}/><Route path="admin" element={<Admin/>}/></Route><Route path="*" element={<Navigate to="/" replace/>}/></Routes></BrowserRouter></VaultProvider>}
