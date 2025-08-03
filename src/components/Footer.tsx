import { Github, Mail, Shield, Code, Twitter, Linkedin, Globe, Heart, ArrowUp } from "lucide-react";

const Footer = () => {
  const links = [
    { name: "Privacy Policy", href: "#privacy", icon: Shield },
    { name: "GitHub", href: "#github", icon: Github },
    { name: "Contact Us", href: "#contact", icon: Mail },
    { name: "Documentation", href: "#docs", icon: Code },
  ];

  const socialLinks = [
    { name: "Twitter", href: "#twitter", icon: Twitter },
    { name: "LinkedIn", href: "#linkedin", icon: Linkedin },
    { name: "Website", href: "#website", icon: Globe },
  ];

  return (
    <footer className="relative bg-gradient-to-t from-background via-card/30 to-background border-t border-border/30 py-20 overflow-hidden">
      {/* Background Pattern */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,hsl(var(--primary)/0.1),transparent_50%)]"></div>
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Main Footer Content */}
        <div className="grid md:grid-cols-4 gap-12 mb-16">
          {/* Brand Section */}
          <div className="md:col-span-2">
            <div className="flex items-center space-x-3 mb-6">
              <div className="relative">
                <div className="w-12 h-12 bg-gradient-to-br from-primary to-accent rounded-xl flex items-center justify-center shadow-lg">
                  <span className="text-primary-foreground font-bold text-xl">E</span>
                </div>
                <div className="absolute -inset-1 bg-gradient-to-r from-primary to-accent rounded-xl blur opacity-20"></div>
              </div>
              <div>
                <h3 className="text-3xl font-bold gradient-text neural-glow">
                  ETHOS
                </h3>
                <p className="text-sm text-muted-foreground">AI Evaluator</p>
              </div>
            </div>
            <p className="text-muted-foreground text-lg leading-relaxed max-w-md mb-6">
              The most comprehensive AI evaluation platform for testing ethical alignment, 
              logical reasoning, and factual accuracy with enterprise-grade precision.
            </p>
            <div className="flex space-x-4">
              {socialLinks.map((link) => {
                const IconComponent = link.icon;
                return (
                  <a
                    key={link.name}
                    href={link.href}
                    className="w-10 h-10 bg-primary/10 hover:bg-primary/20 rounded-lg flex items-center justify-center text-muted-foreground hover:text-primary transition-all duration-300 group"
                  >
                    <IconComponent className="w-5 h-5 group-hover:scale-110 transition-transform duration-300" />
                  </a>
                );
              })}
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h4 className="text-lg font-semibold mb-6 gradient-text">Quick Links</h4>
            <ul className="space-y-4">
              <li><a href="#features" className="text-muted-foreground hover:text-primary transition-colors duration-300">Features</a></li>
              <li><a href="#pricing" className="text-muted-foreground hover:text-primary transition-colors duration-300">Pricing</a></li>
              <li><a href="#docs" className="text-muted-foreground hover:text-primary transition-colors duration-300">Documentation</a></li>
              <li><a href="#api" className="text-muted-foreground hover:text-primary transition-colors duration-300">API</a></li>
            </ul>
          </div>

          {/* Support */}
          <div>
            <h4 className="text-lg font-semibold mb-6 gradient-text">Support</h4>
            <ul className="space-y-4">
              <li><a href="#help" className="text-muted-foreground hover:text-primary transition-colors duration-300">Help Center</a></li>
              <li><a href="#contact" className="text-muted-foreground hover:text-primary transition-colors duration-300">Contact Us</a></li>
              <li><a href="#status" className="text-muted-foreground hover:text-primary transition-colors duration-300">System Status</a></li>
              <li><a href="#community" className="text-muted-foreground hover:text-primary transition-colors duration-300">Community</a></li>
            </ul>
          </div>
        </div>

        {/* Bottom Section */}
        <div className="pt-8 border-t border-border/30">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="flex items-center space-x-2 text-sm text-muted-foreground mb-4 md:mb-0">
              <span>© 2024 ETHOS AI Evaluator. Made with</span>
              <Heart className="w-4 h-4 text-red-500 animate-pulse" />
              <span>for the AI community.</span>
            </div>
            
            <div className="flex items-center space-x-6 text-sm">
              <a href="#privacy" className="text-muted-foreground hover:text-primary transition-colors duration-300">Privacy Policy</a>
              <a href="#terms" className="text-muted-foreground hover:text-primary transition-colors duration-300">Terms of Service</a>
              <span className="text-muted-foreground">v1.0.0-beta</span>
            </div>
          </div>
        </div>
      </div>

      {/* Enhanced Neural Background Elements */}
      <div className="absolute bottom-0 left-0 w-full h-32 overflow-hidden pointer-events-none">
        <div className="absolute bottom-10 left-10 w-4 h-4 bg-gradient-to-r from-primary to-accent rounded-full neural-float shadow-lg" style={{ animationDelay: '0s' }}></div>
        <div className="absolute bottom-5 right-20 w-3 h-3 bg-gradient-to-r from-accent to-primary rounded-full neural-float shadow-lg" style={{ animationDelay: '2s' }}></div>
        <div className="absolute bottom-20 right-1/3 w-5 h-5 bg-gradient-to-r from-primary to-accent rounded-full neural-float shadow-lg" style={{ animationDelay: '4s' }}></div>
        <div className="absolute bottom-15 left-1/4 w-2 h-2 bg-primary/60 rounded-full neural-float" style={{ animationDelay: '1s' }}></div>
        <div className="absolute bottom-25 right-1/2 w-3 h-3 bg-accent/50 rounded-full neural-float" style={{ animationDelay: '3s' }}></div>
      </div>

      {/* Back to Top Button */}
      <button 
        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        className="fixed bottom-8 right-8 w-12 h-12 bg-gradient-to-r from-primary to-accent hover:from-primary/90 hover:to-accent/90 rounded-full flex items-center justify-center text-white shadow-lg hover:shadow-xl transition-all duration-300 group z-50"
      >
        <ArrowUp className="w-5 h-5 group-hover:-translate-y-1 transition-transform duration-300" />
      </button>
    </footer>
  );
};

export default Footer;