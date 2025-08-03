import { Github, Mail, Shield, Code } from "lucide-react";

const Footer = () => {
  const links = [
    { name: "Privacy", href: "#privacy", icon: Shield },
    { name: "GitHub", href: "#github", icon: Github },
    { name: "Contact", href: "#contact", icon: Mail },
    { name: "Version", href: "#version", icon: Code },
  ];

  return (
    <footer className="bg-card/50 border-t border-border/30 py-12">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center">
          {/* Logo and Description */}
          <div className="mb-8 md:mb-0">
            <h3 className="text-2xl font-bold gradient-text neural-glow mb-3">
              ETHOS
            </h3>
            <p className="text-muted-foreground max-w-md">
              AI Behavior Testbed for ethical, logical, and factual evaluation
            </p>
          </div>

          {/* Links */}
          <div className="flex flex-wrap gap-6 md:gap-8">
            {links.map((link) => {
              const IconComponent = link.icon;
              return (
                <a
                  key={link.name}
                  href={link.href}
                  className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors duration-300 hover:neural-glow"
                >
                  <IconComponent className="w-4 h-4" />
                  {link.name}
                </a>
              );
            })}
          </div>
        </div>

        {/* Version and Copyright */}
        <div className="mt-8 pt-8 border-t border-border/30 text-center">
          <div className="flex flex-col md:flex-row justify-between items-center text-sm text-muted-foreground">
            <div>
              © 2024 ETHOS AI Behavior Testbed. All rights reserved.
            </div>
            <div className="mt-2 md:mt-0">
              Version 1.0.0 - Beta
            </div>
          </div>
        </div>

        {/* Neural Background Elements */}
        <div className="absolute bottom-0 left-0 w-full h-32 overflow-hidden pointer-events-none">
          <div className="absolute bottom-10 left-10 w-3 h-3 bg-primary/20 rounded-full neural-float" style={{ animationDelay: '0s' }}></div>
          <div className="absolute bottom-5 right-20 w-2 h-2 bg-accent/30 rounded-full neural-float" style={{ animationDelay: '2s' }}></div>
          <div className="absolute bottom-20 right-1/3 w-4 h-4 bg-primary/15 rounded-full neural-float" style={{ animationDelay: '4s' }}></div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;