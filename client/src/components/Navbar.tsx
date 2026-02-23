import { Button } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import { useState, useEffect } from "react";
import ThemeToggle from "./ThemeToggle";

const Navbar = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navItems = [
    { name: "Product", href: "#product" },
    { name: "Solutions", href: "#solutions" },
    { name: "Pricing", href: "#pricing" },
    { name: "Docs", href: "#docs" },
    { name: "Company", href: "#company" },
  ];

  return (
    <nav className={`fixed top-6 left-1/2 transform -translate-x-1/2 w-[92%] max-w-6xl z-50 transition-all duration-700 rounded-3xl glass-navbar ${
      scrolled 
        ? 'glass-navbar--scrolled' 
        : ''
    }`}>
      <div className="px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex-shrink-0 flex items-center group">
            <div className="w-10 h-10 bg-gradient-to-br from-slate-800/90 to-slate-900/90 rounded-2xl flex items-center justify-center shadow-2xl group-hover:shadow-slate-900/50 transition-all duration-500 group-hover:scale-110 backdrop-blur-md border border-white/30 dark:border-white/20">
              <span className="text-white font-bold text-lg tracking-wider">E</span>
            </div>
            <span className="ml-4 text-2xl font-bold text-slate-900 dark:text-white group-hover:text-slate-700 dark:group-hover:text-gray-200 transition-colors duration-500 tracking-tight">ETHOS</span>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:block">
            <div className="flex items-center space-x-1">
              {navItems.map((item) => (
                <a
                  key={item.name}
                  href={item.href}
                  className="text-slate-700 dark:text-gray-200 hover:text-slate-900 dark:hover:text-white px-5 py-3 text-sm font-medium rounded-2xl glass-nav-item relative group"
                >
                  {item.name}
                  <div className="absolute bottom-1 left-1/2 transform -translate-x-1/2 w-0 h-0.5 bg-slate-800 group-hover:w-6 transition-all duration-500 rounded-full"></div>
                </a>
              ))}
            </div>
          </div>

          {/* CTA Buttons */}
          <div className="hidden md:flex items-center space-x-4">
            <ThemeToggle />
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center space-x-3">
            <ThemeToggle />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="text-slate-700 dark:text-gray-200 glass-nav-item rounded-2xl"
            >
              {isMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </Button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden absolute top-full left-0 right-0 mt-3">
            <div className="mx-4 glass-navbar-mobile rounded-3xl shadow-2xl p-6 space-y-3">
              {navItems.map((item) => (
                <a
                  key={item.name}
                  href={item.href}
                  className="block px-5 py-3 text-base font-medium text-slate-700 dark:text-gray-200 hover:text-slate-900 dark:hover:text-white glass-nav-item rounded-2xl"
                  onClick={() => setIsMenuOpen(false)}
                >
                  {item.name}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;