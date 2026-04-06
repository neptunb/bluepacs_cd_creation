"use client";

import { Box, Container } from "@mui/material";
import Header from "@/components/header";
import NodeSelector from "@/components/node-selector";
import PatientSearch from "@/components/patient-search";
import StudyBrowser from "@/components/study-browser";
import BurnPanel from "@/components/burn-panel";

const HomePage = () => {
  return (
    <main className="min-h-screen bg-gray-50">
      <Header />
      <Container maxWidth="xl" className="py-6 space-y-4">
        <NodeSelector />
        <PatientSearch />
        <StudyBrowser />
        <BurnPanel />
      </Container>
    </main>
  );
};

export default HomePage;
