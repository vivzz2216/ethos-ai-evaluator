import Navbar from "@/components/Navbar";
import HeroSection from "@/components/HeroSection";
import ProcessSection from "@/components/ProcessSection";
import HowItWorks from "@/components/HowItWorks";
import Footer from "@/components/Footer";

interface IndexProps {
  onNavigateToEditor?: () => void;
}

const Index = ({ onNavigateToEditor }: IndexProps) => {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <HeroSection onNavigateToEditor={onNavigateToEditor} />
      <ProcessSection />
      <HowItWorks />
      <Footer />
    </div>
  );
};

export default Index;
