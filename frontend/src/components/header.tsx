"use client";

import { AppBar, Toolbar, Typography, Box } from "@mui/material";
import AlbumIcon from "@mui/icons-material/Album";

const Header = () => {
  return (
    <AppBar position="static" className="bg-blue-800">
      <Toolbar>
        <AlbumIcon className="mr-3" />
        <Typography variant="h6" component="h1" className="font-bold">
          BluePACS CD Creator
        </Typography>
        <Box className="flex-1" />
        <Typography variant="body2" className="text-blue-200">
          DICOM CD/DVD with OHIF Viewer
        </Typography>
      </Toolbar>
    </AppBar>
  );
};

export default Header;
