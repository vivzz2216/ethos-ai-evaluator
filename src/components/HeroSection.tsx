import { Button } from "@/components/ui/button";
import { Github, Zap, Brain, Shield, CheckCircle, ArrowRight, Play, Star, Users, Code } from "lucide-react";

const HeroSection = () => {
  return (
    <section className="relative min-h-screen flex items-center justify-center pt-20 hero-gradient overflow-hidden">
      {/* Background Video */}
      <video 
        autoPlay 
        muted 
        loop 
        className="absolute inset-0 w-full h-full object-cover opacity-15 z-0"
      >
        <source src="/intro.mp4" type="video/mp4" />
      </video>
      
      {/* Enhanced Animated Background Elements */}
      <div className="absolute inset-0 overflow-hidden z-1">
        <div className="absolute top-20 left-10 w-4 h-4 bg-gradient-to-r from-primary to-accent rounded-full neural-float shadow-lg" style={{ animationDelay: '0s' }}></div>
        <div className="absolute top-40 right-20 w-6 h-6 bg-gradient-to-r from-accent to-primary rounded-full neural-float shadow-lg" style={{ animationDelay: '2s' }}></div>
        <div className="absolute bottom-40 left-1/4 w-3 h-3 bg-gradient-to-r from-primary to-accent rounded-full neural-float shadow-lg" style={{ animationDelay: '4s' }}></div>
        <div className="absolute top-60 right-1/3 w-5 h-5 bg-gradient-to-r from-accent to-primary rounded-full neural-float shadow-lg" style={{ animationDelay: '1s' }}></div>
        <div className="absolute bottom-60 right-10 w-4 h-4 bg-gradient-to-r from-primary to-accent rounded-full neural-float shadow-lg" style={{ animationDelay: '3s' }}></div>
        
        {/* Additional floating elements */}
        <div className="absolute top-1/4 left-1/3 w-2 h-2 bg-primary/60 rounded-full neural-float" style={{ animationDelay: '0.5s' }}></div>
        <div className="absolute bottom-1/3 right-1/4 w-3 h-3 bg-accent/50 rounded-full neural-float" style={{ animationDelay: '2.5s' }}></div>
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        {/* Badge */}
        <div className="inline-flex items-center px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary mb-8 animate-fade-in">
          <Star className="w-4 h-4 mr-2" />
          <span className="text-sm font-medium">Trusted by 10,000+ AI Researchers</span>
        </div>

        {/* Main Hero Content */}
        <div className="animate-fade-in-up mb-16">
          <h1 className="text-6xl md:text-8xl font-bold mb-8 leading-tight">
            <span className="gradient-text neural-glow">Evaluate AI</span>
            <br />
            <span className="text-foreground">on Ethics, Logic,</span>
            <br />
            <span className="text-foreground">& Truth</span>
          </h1>
          
          <p className="text-xl md:text-2xl text-muted-foreground mb-12 max-w-4xl mx-auto leading-relaxed">
            The most comprehensive AI evaluation platform. Test your models against ethical frameworks, 
            logical reasoning, and factual accuracy with enterprise-grade precision.
          </p>

          {/* Enhanced CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-6 justify-center mb-16">
            <Button 
              size="lg" 
              className="bg-gradient-to-r from-primary to-accent hover:from-primary/90 hover:to-accent/90 text-primary-foreground shadow-xl hover:shadow-2xl px-8 py-6 text-lg font-semibold group transition-all duration-300"
            >
              <Github className="w-5 h-5 mr-3 group-hover:rotate-12 transition-transform duration-300" />
              Import GitHub Repo
              <ArrowRight className="w-5 h-5 ml-3 group-hover:translate-x-1 transition-transform duration-300" />
            </Button>
            <Button 
              variant="outline" 
              size="lg"
              className="border-2 border-primary/30 hover:bg-primary/10 hover:border-primary/50 px-8 py-6 text-lg font-semibold group transition-all duration-300"
            >
              <Play className="w-5 h-5 mr-3" />
              Try Sample Prompt
            </Button>
          </div>

          {/* Stats */}
          <div className="flex flex-wrap justify-center gap-8 mb-16">
            <div className="flex items-center space-x-2 text-muted-foreground">
              <Users className="w-5 h-5" />
              <span className="font-semibold">10K+ Users</span>
            </div>
            <div className="flex items-center space-x-2 text-muted-foreground">
              <Code className="w-5 h-5" />
              <span className="font-semibold">50K+ Models Tested</span>
            </div>
            <div className="flex items-center space-x-2 text-muted-foreground">
              <Star className="w-5 h-5" />
              <span className="font-semibold">99.9% Accuracy</span>
            </div>
          </div>
        </div>

                 
      </div>
    </section>
  );
};

export default HeroSection;