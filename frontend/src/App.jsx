import React, { useState } from 'react';
import './App.css';
import Sidebar from './components/Sidebar';
import GridStatus from './pages/GridStatus';
import Intelligence from './pages/Intelligence';
import DispatchLog from './pages/DispatchLog';
import Simulation from './pages/Simulation';

const PAGES = {
  grid:         GridStatus,
  intelligence: Intelligence,
  dispatch:     DispatchLog,
  simulation:   Simulation,
};

export default function App() {
  const [active, setActive] = useState('grid');
  const Page = PAGES[active] || GridStatus;

  return (
    <div className="app">
      <Sidebar active={active} onSelect={setActive} />
      <main className="app__main">
        <Page />
      </main>
    </div>
  );
}
