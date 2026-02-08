import { ArrowRight, Play, Code } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useEffect } from "react";

interface HeroSectionProps {
  onNavigateToEditor?: () => void;
}

const HeroSection = ({ onNavigateToEditor }: HeroSectionProps) => {
  useEffect(() => {
    // Load Spline viewer script with delay to ensure DOM is ready
    const loadSplineScript = () => {
      // Check if script already exists
      const existingScript = document.querySelector('script[src*="spline-viewer"]');
      if (existingScript) {
        return existingScript;
      }

      const script = document.createElement('script');
      script.type = 'module';
      script.src = 'https://unpkg.com/@splinetool/viewer@1.10.72/build/spline-viewer.js';
      document.head.appendChild(script);
      return script;
    };

    // Delay script loading to ensure containers are properly sized
    const timeoutId = setTimeout(loadSplineScript, 500);

    return () => {
      clearTimeout(timeoutId);
    };
  }, []);

  return (
    <section className="relative pt-32 pb-20 overflow-hidden min-h-screen bg-white dark:bg-black transition-colors duration-300">
      {/* Background Image for Light Mode */}
      <div className="absolute inset-0 bg-white/20 dark:bg-black/70">
        <div className="absolute inset-0 bg-[url('/aisle-blur.jpg')] bg-cover bg-center bg-no-repeat block dark:hidden"></div>
        <div className="absolute inset-0 bg-[url('/blackbg.jpg')] bg-cover bg-center bg-no-repeat hidden dark:block"></div>
      </div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-full">
        <div className="grid grid-cols-1 gap-8 lg:gap-12 items-center h-full min-h-[80vh]">
          
          {/* Content - Centered in both light and dark mode */}
          <div className="text-center z-10 max-w-4xl mx-auto">
            {/* Main Headline */}
            <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-4xl xl:text-5xl font-bold tracking-tight text-black dark:text-white mb-6 lg:mb-8 leading-tight transition-colors duration-300 whitespace-nowrap">
              Ethical Logical and Reasoning Testbed
            </h1>

            {/* Subheadline */}
            <p className="text-sm sm:text-base lg:text-base xl:text-lg text-gray-600 dark:text-gray-300 mb-1 lg:mb-2 leading-relaxed transition-colors duration-300">
              Evaluate ethical alignment, logical reasoning, and factual accuracy before deployment. Ensure responsible, trustworthy outputs
            </p>

            {/* Spline Viewer for Light Mode - Under the text */}
            <div className="relative w-full h-[400px] sm:h-[500px] lg:h-[600px] xl:h-[700px] mb-4 lg:mb-6 block dark:hidden min-h-[400px] bg-transparent overflow-hidden">
              {/* ETHOS 3D Text - Behind/Over the Spline */}
              <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
                <h2 className="glass-ethos-text text-8xl sm:text-9xl lg:text-[12rem] xl:text-[14rem] font-black tracking-wider opacity-30 dark:opacity-50 text-transparent bg-clip-text bg-gradient-to-br from-blue-400 via-purple-500 to-pink-500 dark:from-blue-200 dark:via-purple-300 dark:to-pink-300">
                  ETHOS
                </h2>
              </div>
              <spline-viewer 
                url="https://prod.spline.design/uT81TnuW-q4BIFT3/scene.splinecode"
                style={{
                  width: '100%',
                  height: '100%',
                  minWidth: '400px',
                  minHeight: '400px',
                  pointerEvents: 'none',
                  display: 'block',
                  backgroundColor: 'transparent',
                  border: 'none',
                  outline: 'none'
                }}
                onError={(e: any) => {
                  console.warn('Spline viewer error:', e);
                  // Hide the viewer on error to prevent WebGL spam
                  const viewer = e.target;
                  if (viewer) {
                    viewer.style.display = 'none';
                  }
                }}
                onLoad={() => {
                  console.log('Spline viewer loaded successfully');
                }}
              />
            </div>

            {/* Spline Viewer for Dark Mode - Under the text */}
            <div className="relative w-full h-[400px] sm:h-[500px] lg:h-[600px] xl:h-[700px] mb-4 lg:mb-6 hidden dark:block min-h-[400px] bg-transparent overflow-hidden">
              {/* ETHOS 3D Text - Behind/Over the Spline */}
              <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
                <h2 className="glass-ethos-text text-8xl sm:text-9xl lg:text-[12rem] xl:text-[14rem] font-black tracking-wider opacity-30 dark:opacity-50 text-transparent bg-clip-text bg-gradient-to-br from-blue-400 via-purple-500 to-pink-500 dark:from-blue-200 dark:via-purple-300 dark:to-pink-300">
                  ETHOS
                </h2>
              </div>
              <spline-viewer 
                url="https://prod.spline.design/uT81TnuW-q4BIFT3/scene.splinecode"
                style={{
                  width: '100%',
                  height: '100%',
                  minWidth: '400px',
                  minHeight: '400px',
                  pointerEvents: 'none',
                  display: 'block',
                  backgroundColor: 'transparent',
                  border: 'none',
                  outline: 'none'
                }}
                onError={(e: any) => {
                  console.warn('Spline viewer error:', e);
                  // Hide the viewer on error to prevent WebGL spam
                  const viewer = e.target;
                  if (viewer) {
                    viewer.style.display = 'none';
                  }
                }}
                onLoad={() => {
                  console.log('Spline viewer loaded successfully');
                }}
              />
            </div>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button 
                variant="default" 
                size="lg"
                className="px-6 lg:px-8 py-3 lg:py-4 text-base lg:text-lg font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-all duration-300 group"
              >
                Get Started
                <ArrowRight className="w-4 lg:w-5 h-4 lg:h-5 ml-2 group-hover:translate-x-1 transition-transform duration-300" />
              </Button>
              <Button 
                variant="outline" 
                size="lg"
                onClick={onNavigateToEditor}
                className="px-6 lg:px-8 py-3 lg:py-4 text-base lg:text-lg font-semibold border-2 border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 text-gray-700 dark:text-white hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800 transition-all duration-300 group"
              >
                <Code className="w-4 lg:w-5 h-4 lg:h-5 mr-2" />
                Try Editor
              </Button>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
};

export default HeroSection;