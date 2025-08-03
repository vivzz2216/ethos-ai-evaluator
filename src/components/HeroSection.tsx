import { Button } from "@/components/ui/button";
import { Github, Zap, Brain, Shield, CheckCircle } from "lucide-react";
import ethicalIcon from "@/assets/ethical-icon.png";
import logicalIcon from "@/assets/logical-icon.png";
import factualIcon from "@/assets/factual-icon.png";

const HeroSection = () => {
  return (
    <section className="relative min-h-screen flex items-center justify-center pt-16 hero-gradient">
      {/* Animated Background Elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-20 left-10 w-4 h-4 bg-primary/30 rounded-full neural-float" style={{ animationDelay: '0s' }}></div>
        <div className="absolute top-40 right-20 w-6 h-6 bg-accent/40 rounded-full neural-float" style={{ animationDelay: '2s' }}></div>
        <div className="absolute bottom-40 left-1/4 w-3 h-3 bg-primary/50 rounded-full neural-float" style={{ animationDelay: '4s' }}></div>
        <div className="absolute top-60 right-1/3 w-5 h-5 bg-accent/30 rounded-full neural-float" style={{ animationDelay: '1s' }}></div>
        <div className="absolute bottom-60 right-10 w-4 h-4 bg-primary/40 rounded-full neural-float" style={{ animationDelay: '3s' }}></div>
      </div>

      <div className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        {/* Main Hero Content */}
        <div className="animate-fade-in-up">
          <h1 className="text-5xl md:text-7xl font-bold mb-6 leading-tight">
            <span className="gradient-text neural-glow">Evaluate AI</span>
            <br />
            <span className="text-foreground">on Ethics, Logic,</span>
            <br />
            <span className="text-foreground">and Truth</span>
          </h1>
          
          <p className="text-xl md:text-2xl text-muted-foreground mb-12 max-w-3xl mx-auto leading-relaxed">
            Plug in your AI models and test their ethical, logical, and factual responses
            with our comprehensive evaluation platform.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
            <Button 
              size="lg" 
              className="bg-primary hover:bg-primary/90 text-primary-foreground animate-pulse-glow px-8 py-4 text-lg font-semibold"
            >
              <Github className="w-5 h-5 mr-2" />
              Import GitHub Repo
            </Button>
            <Button 
              variant="outline" 
              size="lg"
              className="border-primary/30 hover:bg-primary/10 px-8 py-4 text-lg font-semibold"
            >
              <Zap className="w-5 h-5 mr-2" />
              Try Sample Prompt
            </Button>
          </div>
        </div>

        {/* Three Pillars */}
        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          <div className="glass-card p-8 text-center group hover:scale-105 transition-all duration-500">
            <div className="mb-6 flex justify-center">
              <img 
                src={ethicalIcon} 
                alt="Ethical Alignment" 
                className="w-16 h-16 neural-float"
                style={{ animationDelay: '0.5s' }}
              />
            </div>
            <h3 className="text-xl font-bold mb-3 gradient-text">Ethical Alignment</h3>
            <p className="text-muted-foreground">
              Test AI responses against ethical frameworks and moral reasoning principles.
            </p>
          </div>

          <div className="glass-card p-8 text-center group hover:scale-105 transition-all duration-500">
            <div className="mb-6 flex justify-center">
              <img 
                src={logicalIcon} 
                alt="Logical Reasoning" 
                className="w-16 h-16 neural-float"
                style={{ animationDelay: '1s' }}
              />
            </div>
            <h3 className="text-xl font-bold mb-3 gradient-text">Logical Reasoning</h3>
            <p className="text-muted-foreground">
              Evaluate logical consistency, deductive reasoning, and problem-solving capabilities.
            </p>
          </div>

          <div className="glass-card p-8 text-center group hover:scale-105 transition-all duration-500">
            <div className="mb-6 flex justify-center">
              <img 
                src={factualIcon} 
                alt="Factual Accuracy" 
                className="w-16 h-16 neural-float"
                style={{ animationDelay: '1.5s' }}
              />
            </div>
            <h3 className="text-xl font-bold mb-3 gradient-text">Factual Accuracy</h3>
            <p className="text-muted-foreground">
              Verify factual claims, data accuracy, and information reliability.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;