"use client";

import { Container } from "@mui/material";
import CdAccessGate from "@/components/cd-access-gate";
import Header from "@/components/header";
import NodeSelector from "@/components/node-selector";
import PatientSearch from "@/components/patient-search";
import StudyBrowser from "@/components/study-browser";
import BurnPanel from "@/components/burn-panel";

const HomePage = () => {
  return (
    <main className="min-h-screen bg-gray-50">
      <Header />
      <CdAccessGate>
        <Container maxWidth="xl" className="space-y-4 py-6">
          <NodeSelector />
          <PatientSearch />
          <StudyBrowser />
          <BurnPanel />
        </Container>
      </CdAccessGate>
    </main>
  );
};

export default HomePage;
