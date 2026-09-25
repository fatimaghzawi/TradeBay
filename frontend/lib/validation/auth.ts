import {
  emailSchema,
  passwordSchema,
  requiredText,
} from "@/lib/validation/common";
import { z } from "zod";

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(8, "Password must be at least 8 characters"),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

const registerBaseSchema = z.object({
  first_name: requiredText("First name", 100),
  last_name: requiredText("Last name", 100),
  email: emailSchema,
  password: passwordSchema,
  confirmPassword: z.string(),
  business_name: z.string().optional(),
  business_type: z.enum(["buyer", "supplier"]).optional(),
  invitation_token: z.string().optional(),
});

export const registerSchema = registerBaseSchema
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  })
  .superRefine((data, ctx) => {
    
    if (data.invitation_token) return;
    if (!data.business_name?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Business name is required",
        path: ["business_name"],
      });
    }
    if (!data.business_type) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Select buyer or supplier",
        path: ["business_type"],
      });
    }
  });

export type RegisterFormValues = z.infer<typeof registerSchema>;

export const forgotPasswordSchema = z.object({
  email: emailSchema,
});

export type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: passwordSchema,
    confirmPassword: z.string(),
  })
  .refine((data) => data.new_password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

export type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>;
