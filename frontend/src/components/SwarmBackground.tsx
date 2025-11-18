import React, { useEffect, useRef } from 'react';

interface Boid {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
}

export const SwarmBackground: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let boids: Boid[] = [];
    
    // Configuration
    const boidCount = 100; // Increased count
    const speed = 1.5; // Increased speed
    const turnSpeed = 0.1;
    const perceptionRadius = 120;
    const separationDistance = 30;

    const resizeCanvas = () => {
      // Set actual canvas size to window size for sharp rendering
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    const createBoids = () => {
      boids = [];
      for (let i = 0; i < boidCount; i++) {
        boids.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * speed * 2,
          vy: (Math.random() - 0.5) * speed * 2,
          size: Math.random() * 2 + 2, // Slightly larger
        });
      }
    };

    const drawBoid = (boid: Boid) => {
      const angle = Math.atan2(boid.vy, boid.vx);
      
      ctx.save();
      ctx.translate(boid.x, boid.y);
      ctx.rotate(angle);
      
      // Draw Nanobot shape (futuristic chevron)
      ctx.beginPath();
      ctx.moveTo(8, 0);
      ctx.lineTo(-5, 4);
      ctx.lineTo(-2, 0);
      ctx.lineTo(-5, -4);
      ctx.closePath();
      
      // Neon Cyan/Blue for Nanobots
      ctx.fillStyle = '#00f2ff'; 
      ctx.shadowBlur = 10;
      ctx.shadowColor = '#00f2ff';
      ctx.fill();
      
      ctx.restore();
    };

    const updateBoids = () => {
      boids.forEach(boid => {
        let separationX = 0;
        let separationY = 0;
        let alignmentX = 0;
        let alignmentY = 0;
        let cohesionX = 0;
        let cohesionY = 0;
        let neighborCount = 0;

        boids.forEach(other => {
          if (boid === other) return;

          const dx = other.x - boid.x;
          const dy = other.y - boid.y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < perceptionRadius) {
            alignmentX += other.vx;
            alignmentY += other.vy;
            cohesionX += other.x;
            cohesionY += other.y;

            if (distance < separationDistance) {
              separationX -= dx;
              separationY -= dy;
            }
            neighborCount++;
          }
        });

        if (neighborCount > 0) {
          alignmentX /= neighborCount;
          alignmentY /= neighborCount;
          cohesionX /= neighborCount;
          cohesionY /= neighborCount;
          
          cohesionX = (cohesionX - boid.x) * 0.01;
          cohesionY = (cohesionY - boid.y) * 0.01;
        }

        boid.vx += (separationX * 0.05) + (alignmentX * 0.02) + (cohesionX * 0.02);
        boid.vy += (separationY * 0.05) + (alignmentY * 0.02) + (cohesionY * 0.02);

        const velocity = Math.sqrt(boid.vx * boid.vx + boid.vy * boid.vy);
        if (velocity > speed) {
          boid.vx = (boid.vx / velocity) * speed;
          boid.vy = (boid.vy / velocity) * speed;
        } else if (velocity < speed * 0.5) {
           boid.vx = (boid.vx / velocity) * speed * 0.5;
           boid.vy = (boid.vy / velocity) * speed * 0.5;
        }
        
        boid.vx += (Math.random() - 0.5) * turnSpeed;
        boid.vy += (Math.random() - 0.5) * turnSpeed;

        boid.x += boid.vx;
        boid.y += boid.vy;

        if (boid.x < -20) boid.x = canvas.width + 20;
        if (boid.x > canvas.width + 20) boid.x = -20;
        if (boid.y < -20) boid.y = canvas.height + 20;
        if (boid.y > canvas.height + 20) boid.y = -20;
      });
    };

    const animate = () => {
      // Fade effect for trails
      ctx.fillStyle = 'rgba(10, 10, 10, 0.2)'; // Semi-transparent black for trails
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      
      // Draw connections
      ctx.lineWidth = 0.5;
      
      boids.forEach((boid, i) => {
        // Connect nearby boids
        boids.slice(i + 1).forEach(other => {
            const dx = other.x - boid.x;
            const dy = other.y - boid.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            if (distance < 100) {
                ctx.beginPath();
                ctx.moveTo(boid.x, boid.y);
                ctx.lineTo(other.x, other.y);
                const opacity = 1 - (distance / 100);
                ctx.strokeStyle = `rgba(0, 242, 255, ${opacity * 0.2})`;
                ctx.stroke();
            }
        });
        
        drawBoid(boid);
      });
      
      updateBoids();
      animationFrameId = requestAnimationFrame(animate);
    };

    resizeCanvas();
    createBoids();
    animate();

    window.addEventListener('resize', resizeCanvas);

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas 
      ref={canvasRef} 
      className="absolute inset-0 w-full h-full"
      style={{ background: '#0a0a0a' }}
    />
  );
};
