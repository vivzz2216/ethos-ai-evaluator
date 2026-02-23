import { Twitter, Linkedin, Github, Shield, Zap, BarChart3 } from "lucide-react";

const Footer = () => {
  const productLinks = [
    { name: "Ethics Testing", href: "#ethics" },
    { name: "Logic Evaluation", href: "#logic" },
    { name: "Fact Checking", href: "#facts" },
    { name: "API Documentation", href: "#api" },
  ];

  const companyLinks = [
    { name: "About ETHOS", href: "#about" },
    { name: "Research", href: "#research" },
    { name: "Careers", href: "#careers" },
    { name: "Contact", href: "#contact" },
  ];

  const resourceLinks = [
    { name: "Getting Started", href: "#docs" },
    { name: "Model Guidelines", href: "#guides" },
    { name: "Best Practices", href: "#practices" },
    { name: "System Status", href: "#status" },
  ];

  const complianceLinks = [
    { name: "Privacy Policy", href: "#privacy" },
    { name: "Terms of Service", href: "#terms" },
    { name: "SOC 2 Report", href: "#soc2" },
    { name: "Security", href: "#security" },
  ];

  const socialLinks = [
    { name: "Twitter", href: "#twitter", icon: Twitter },
    { name: "LinkedIn", href: "#linkedin", icon: Linkedin },
    { name: "GitHub", href: "#github", icon: Github },
  ];

  const stats = [
    { icon: Zap, label: "< 60s", description: "Average test time" },
    { icon: Shield, label: "SOC 2", description: "Certified security" },
    { icon: BarChart3, label: "99.7%", description: "Detection accuracy" },
  ];

  return (
    <footer className="bg-black dark:bg-gray-950 border-t border-gray-800 dark:border-gray-700 transition-colors duration-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">


        <div className="grid grid-cols-2 md:grid-cols-6 gap-8">
          {/* Logo and Description */}
          <div className="col-span-2">
            <div className="flex items-center mb-4">
              <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg">
                <span className="text-white font-bold text-lg">E</span>
              </div>
              <span className="ml-3 text-2xl font-bold text-white">ETHOS</span>
            </div>
            <p className="text-gray-400 mb-6 max-w-sm leading-relaxed">
              The most trusted AI evaluation platform. Test your models for ethics, logic, and accuracy before deployment.
            </p>
            <div className="flex space-x-3">
              {socialLinks.map((link) => {
                const IconComponent = link.icon;
                return (
                  <a
                    key={link.name}
                    href={link.href}
                    className="w-11 h-11 bg-gray-800 hover:bg-gray-700 rounded-xl flex items-center justify-center text-gray-400 hover:text-white transition-all duration-200 border border-gray-700 hover:border-gray-600"
                  >
                    <IconComponent className="w-5 h-5" />
                  </a>
                );
              })}
            </div>
          </div>

          {/* Product Links */}
          <div>
            <h4 className="font-semibold text-white mb-4">Testing Suite</h4>
            <ul className="space-y-3">
              {productLinks.map((link) => (
                <li key={link.name}>
                  <a href={link.href} className="text-gray-400 hover:text-white text-sm transition-colors duration-200 hover:underline">
                    {link.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Company Links */}
          <div>
            <h4 className="font-semibold text-white mb-4">Company</h4>
            <ul className="space-y-3">
              {companyLinks.map((link) => (
                <li key={link.name}>
                  <a href={link.href} className="text-gray-400 hover:text-white text-sm transition-colors duration-200 hover:underline">
                    {link.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources Links */}
          <div>
            <h4 className="font-semibold text-white mb-4">Resources</h4>
            <ul className="space-y-3">
              {resourceLinks.map((link) => (
                <li key={link.name}>
                  <a href={link.href} className="text-gray-400 hover:text-white text-sm transition-colors duration-200 hover:underline">
                    {link.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Compliance Links */}
          <div>
            <h4 className="font-semibold text-white mb-4">Compliance</h4>
            <ul className="space-y-3">
              {complianceLinks.map((link) => (
                <li key={link.name}>
                  <a href={link.href} className="text-gray-400 hover:text-white text-sm transition-colors duration-200 hover:underline">
                    {link.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="border-t border-gray-800 mt-12 pt-8">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <p className="text-gray-500 text-sm">
              © 2024 ETHOS. All rights reserved. Built for responsible AI deployment.
            </p>
            <div className="flex items-center space-x-6 mt-4 md:mt-0">
              <span className="text-gray-500 text-xs">Enterprise-grade security</span>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-gray-500 text-xs">All systems operational</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;