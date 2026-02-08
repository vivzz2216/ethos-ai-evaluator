import { TooltipProvider } from "@/components/ui/tooltip";
import Index from "./pages/Index";
import Editor from "./pages/Editor";
import { useState } from "react";

const App = () => {
  const [currentPage, setCurrentPage] = useState<'home' | 'editor'>('home');

  const navigateToEditor = () => {
    setCurrentPage('editor');
  };

  const navigateToHome = () => {
    setCurrentPage('home');
  };

  return (
    <TooltipProvider>
      {currentPage === 'home' ? (
        <Index onNavigateToEditor={navigateToEditor} />
      ) : (
        <Editor />
      )}
    </TooltipProvider>
  );
};

export default App;
