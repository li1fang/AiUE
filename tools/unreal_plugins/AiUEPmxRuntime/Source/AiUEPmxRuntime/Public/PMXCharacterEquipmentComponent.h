#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/SkeletalMesh.h"
#include "PMXCharacterEquipmentComponent.generated.h"

class USkeletalMeshComponent;

UCLASS(ClassGroup=(PMXPipeline), BlueprintType, Blueprintable, meta=(BlueprintSpawnableComponent))
class AIUEPMXRUNTIME_API UPMXCharacterEquipmentComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UPMXCharacterEquipmentComponent();

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void SetDesiredWeaponMesh(USkeletalMesh* InWeaponMesh);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    USkeletalMesh* GetDesiredWeaponMesh() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void SetAttachSocketName(FName InAttachSocketName);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    FName GetAttachSocketName() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    USkeletalMeshComponent* ApplyWeaponMeshToOwner();

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    USkeletalMeshComponent* GetManagedWeaponMeshComponent() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    FName GetResolvedAttachSocketName() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    bool HasResolvedAttachSocket() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    FString GetAttachResolutionMode() const;

protected:
    virtual void BeginPlay() override;

private:
    USkeletalMeshComponent* EnsureManagedMeshComponent();
    USkeletalMeshComponent* FindOwnerMeshComponent() const;
    FName ResolveAttachSocketName(USkeletalMeshComponent* OwnerMesh);
    void RefreshManagedMeshComponent(USkeletalMeshComponent* MeshComponent) const;

private:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline", meta=(AllowPrivateAccess="true"))
    TObjectPtr<USkeletalMesh> DesiredWeaponMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline", meta=(AllowPrivateAccess="true"))
    FName AttachSocketName = TEXT("WeaponSocket");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline", meta=(AllowPrivateAccess="true"))
    bool bCreateComponentIfMissing = true;

    UPROPERTY(Transient)
    TObjectPtr<USkeletalMeshComponent> ManagedWeaponMeshComponent;

    UPROPERTY(Transient)
    FName ResolvedAttachSocketName = NAME_None;

    UPROPERTY(Transient)
    bool bResolvedAttachSocketExists = false;

    UPROPERTY(Transient)
    FString AttachResolutionMode = TEXT("unresolved");
};
